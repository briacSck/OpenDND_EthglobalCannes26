/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import Foundation
import SwiftUI
import Combine
import DynamicSDKSwift

@MainActor
final class WalletViewModel: ObservableObject {
  @Published var isAuthenticated = false
  @Published var wallets: [BaseWallet] = []
  @Published var isLoading = false
  @Published var isCreatingWallet = false
  @Published var errorMessage: String?
  @Published var userEmail: String?
  @Published var showEmailOtpSheet = false
  @Published var email = ""

  private var sdk: DynamicSDK? { DynamicSDK.shared }
  private var cancellables = Set<AnyCancellable>()
  private var authCheckRetries = 0

  func startListening() {
    guard let sdk else { return }

    // Check if already authenticated
    if let user = sdk.auth.authenticatedUser {
      isAuthenticated = true
      loadWallets()
      userEmail = user.email
      persistAuthState(true)
    } else if wasAuthenticated {
      // SDK might need a moment to restore session from keychain
      retryAuthCheck()
    }

    // Listen for auth state changes
    sdk.auth.authenticatedUserChanges
      .receive(on: DispatchQueue.main)
      .sink { [weak self] user in
        guard let self else { return }
        if user != nil {
          self.isAuthenticated = true
          self.userEmail = user?.email
          self.loadWallets()
          self.persistAuthState(true)
        } else {
          self.isAuthenticated = false
          self.wallets = []
          self.userEmail = nil
          self.persistAuthState(false)
        }
      }
      .store(in: &cancellables)

    // Listen for wallet changes
    sdk.wallets.userWalletsChanges
      .receive(on: DispatchQueue.main)
      .sink { [weak self] wallets in
        self?.wallets = wallets
      }
      .store(in: &cancellables)
  }

  func stopListening() {
    cancellables.removeAll()
  }

  func loadWallets() {
    guard let sdk else { return }
    wallets = sdk.wallets.userWallets
  }

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

  func verifyEmailOTP(code: String) async throws {
    guard let sdk else { return }
    try await sdk.auth.email.verifyOTP(token: code)
  }

  func openAuthFlow() {
    sdk?.ui.showAuth()
  }

  func createWallet(chain: EmbeddedWalletChain = .evm) async {
    guard let sdk else { return }
    isCreatingWallet = true
    errorMessage = nil

    do {
      _ = try await sdk.wallets.embedded.createWallet(chain: chain)
      loadWallets()
    } catch {
      errorMessage = error.localizedDescription
    }
    isCreatingWallet = false
  }

  func logout() {
    Task {
      try? await sdk?.auth.logout()
      persistAuthState(false)
    }
  }

  var primaryWalletAddress: String? {
    wallets.first?.address
  }

  var truncatedAddress: String {
    guard let addr = primaryWalletAddress, addr.count > 12 else {
      return primaryWalletAddress ?? ""
    }
    return "\(addr.prefix(6))...\(addr.suffix(4))"
  }

  // MARK: - Auth Persistence

  private var wasAuthenticated: Bool {
    UserDefaults.standard.bool(forKey: "dynamicWasAuthenticated")
  }

  private func persistAuthState(_ authenticated: Bool) {
    UserDefaults.standard.set(authenticated, forKey: "dynamicWasAuthenticated")
  }

  /// Dynamic SDK may take a moment to restore the session from keychain on cold start.
  /// Retry a few times before giving up.
  private func retryAuthCheck() {
    guard authCheckRetries < 5 else { return }
    authCheckRetries += 1

    DispatchQueue.main.asyncAfter(deadline: .now() + Double(authCheckRetries) * 0.5) { [weak self] in
      guard let self, let sdk = self.sdk else { return }
      if let user = sdk.auth.authenticatedUser {
        self.isAuthenticated = true
        self.userEmail = user.email
        self.loadWallets()
      } else {
        self.retryAuthCheck()
      }
    }
  }
}
