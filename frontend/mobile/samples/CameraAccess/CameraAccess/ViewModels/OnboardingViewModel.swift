import Foundation
import SwiftUI
import Combine
import DynamicSDKSwift

enum OnboardingStep: Int, CaseIterable {
  case name = 0
  case goal
  case email
  case budget
  case difficulty
  case frequency
  case pool
  case friends
  case wallet
}

struct FriendEntry: Identifiable {
  let id = UUID()
  var phone: String
}

@MainActor
final class OnboardingViewModel: ObservableObject {
  @Published var currentStep: OnboardingStep = .name
  @Published var firstName = ""
  @Published var generalGoal = ""
  @Published var email = ""
  @Published var questBudget: Double = 25
  @Published var difficulty: Int = 1 // 0=easy, 1=medium, 2=hard, 3=extreme
  @Published var frequency: Int = 1 // 0=daily, 1=weekly, 2=biweekly, 3=monthly
  @Published var poolAmount: Double = 50
  @Published var friends: [FriendEntry] = [FriendEntry(phone: "")]
  @Published var groupMode: Int = 0 // 0=create, 1=join
  @Published var groupName = ""

  @Published var isLoading = false
  @Published var showEmailOtpSheet = false
  @Published var otpCode = ""
  @Published var errorMessage: String?
  @Published var emailVerified = false
  @Published var walletCreated = false
  @Published var isCreatingWallet = false

  private var sdk: DynamicSDK? { DynamicSDK.shared }
  private var cancellables = Set<AnyCancellable>()

  var totalSteps: Int { OnboardingStep.allCases.count }
  var progress: Double { Double(currentStep.rawValue + 1) / Double(totalSteps) }

  var canContinue: Bool {
    switch currentStep {
    case .name: return !firstName.trimmingCharacters(in: .whitespaces).isEmpty
    case .goal: return !generalGoal.trimmingCharacters(in: .whitespaces).isEmpty
    case .email: return emailVerified
    case .budget: return true
    case .difficulty: return true
    case .frequency: return true
    case .pool: return poolAmount > 0
    case .friends: return groupMode == 1 ? !groupName.isEmpty : friends.contains { !$0.phone.isEmpty }
    case .wallet: return walletCreated || sdk?.auth.authenticatedUser != nil
    }
  }

  var isLastStep: Bool { currentStep == .wallet }

  func next() {
    guard let nextStep = OnboardingStep(rawValue: currentStep.rawValue + 1) else { return }
    withAnimation(.easeInOut(duration: 0.3)) {
      currentStep = nextStep
    }
  }

  func back() {
    guard let prevStep = OnboardingStep(rawValue: currentStep.rawValue - 1) else { return }
    withAnimation(.easeInOut(duration: 0.3)) {
      currentStep = prevStep
    }
  }

  // MARK: - Email OTP

  func sendEmailOTP() {
    guard let sdk, !email.isEmpty else { return }
    isLoading = true
    errorMessage = nil

    Task {
      do {
        try await sdk.auth.email.sendOTP(email: email)
        isLoading = false
        showEmailOtpSheet = true
      } catch {
        isLoading = false
        errorMessage = error.localizedDescription
      }
    }
  }

  func verifyEmailOTP() async {
    guard let sdk, !otpCode.isEmpty else { return }
    isLoading = true
    do {
      try await sdk.auth.email.verifyOTP(token: otpCode)
      emailVerified = true
      showEmailOtpSheet = false
      otpCode = ""
      isLoading = false
    } catch {
      errorMessage = error.localizedDescription
      isLoading = false
    }
  }

  // MARK: - Wallet

  func checkExistingWallet() {
    guard let sdk else { return }
    if sdk.wallets.embedded.hasWallet || !sdk.wallets.userWallets.isEmpty {
      walletCreated = true
    }
  }

  func createWallet() async {
    guard let sdk else { return }
    isCreatingWallet = true
    errorMessage = nil

    // Check if wallet already exists
    if sdk.wallets.embedded.hasWallet || !sdk.wallets.userWallets.isEmpty {
      walletCreated = true
      isCreatingWallet = false
      return
    }

    do {
      _ = try await sdk.wallets.embedded.createWallet(chain: .evm)
      walletCreated = true
    } catch {
      // If embedded wallet creation fails, try getting existing wallet
      do {
        if let existing = try await sdk.wallets.embedded.getWallet() {
          _ = existing
          walletCreated = true
        } else {
          errorMessage = error.localizedDescription
        }
      } catch {
        errorMessage = "Wallet creation failed. Make sure embedded wallets are enabled in your Dynamic dashboard."
      }
    }
    isCreatingWallet = false
  }

  func openDynamicAuth() {
    guard let sdk else { return }
    // Use Dynamic's built-in auth UI which handles wallet provisioning
    sdk.ui.showAuth()

    // Listen for wallet changes
    sdk.wallets.userWalletsChanges
      .receive(on: DispatchQueue.main)
      .sink { [weak self] wallets in
        if !wallets.isEmpty {
          self?.walletCreated = true
        }
      }
      .store(in: &cancellables)

    // Also listen for embedded wallet
    sdk.wallets.embedded.hasWalletChanges
      .receive(on: DispatchQueue.main)
      .sink { [weak self] hasWallet in
        if hasWallet {
          self?.walletCreated = true
        }
      }
      .store(in: &cancellables)
  }

  // MARK: - Friends

  func addFriend() {
    friends.append(FriendEntry(phone: ""))
  }

  func removeFriend(at index: Int) {
    guard friends.count > 1 else { return }
    friends.remove(at: index)
  }

  // MARK: - Submit to server

  @Published var isSaving = false

  func submitOnboarding() async -> Bool {
    isSaving = true
    errorMessage = nil

    let walletAddress = sdk?.wallets.userWallets.first?.address

    let friendPhones = friends
      .map { $0.phone.trimmingCharacters(in: .whitespaces) }
      .filter { !$0.isEmpty }

    let body: [String: Any] = [
      "firstName": firstName,
      "email": email,
      "generalGoal": generalGoal,
      "questBudget": questBudget,
      "difficulty": difficulty,
      "frequency": frequency,
      "poolAmount": poolAmount,
      "groupMode": groupMode,
      "groupName": groupName,
      "friends": friendPhones,
      "walletAddress": walletAddress ?? "",
    ]

    guard let url = URL(string: "\(Self.serverURL)/api/users") else {
      errorMessage = "Invalid server URL"
      isSaving = false
      return false
    }

    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.timeoutInterval = 10

    do {
      request.httpBody = try JSONSerialization.data(withJSONObject: body)
      NSLog("[Onboarding] POST to \(Self.serverURL)/api/users with body: \(body)")
      let (data, response) = try await URLSession.shared.data(for: request)

      guard let http = response as? HTTPURLResponse else {
        NSLog("[Onboarding] No HTTP response")
        errorMessage = "No server response"
        isSaving = false
        return false
      }

      let responseBody = String(data: data, encoding: .utf8) ?? ""
      NSLog("[Onboarding] Response \(http.statusCode): \(responseBody)")

      if http.statusCode == 201 {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let userId = json["id"] as? String {
          UserDefaults.standard.set(userId, forKey: "userId")
        }
        isSaving = false
        return true
      } else if http.statusCode == 409 {
        isSaving = false
        return true
      } else {
        errorMessage = "Server error (\(http.statusCode))"
        isSaving = false
        return false
      }
    } catch {
      errorMessage = "Could not reach server: \(error.localizedDescription)"
      isSaving = false
      return false
    }
  }

  // Server address — use local network IP so the phone can reach the Mac
  private static let serverURL = "http://10.105.177.116:3002"

  // MARK: - Formatting

  let difficultyOptions = ["Easy", "Medium", "Hard", "Extreme"]
  let frequencyOptions = ["Daily", "Weekly", "Biweekly", "Monthly"]
}
