import SwiftUI
import DynamicSDKSwift

struct OnboardingView: View {
  @StateObject private var vm = OnboardingViewModel()
  let onComplete: () -> Void

  var body: some View {
    VStack(spacing: 0) {
      // Progress bar
      progressBar

      // Content
      ScrollView {
        VStack(spacing: 0) {
          stepContent
            .padding(.horizontal, 20)
            .padding(.top, 24)
            .padding(.bottom, 20)
        }
      }

      // Navigation buttons
      bottomButtons
    }
    .background(Color.white)
    .sheet(isPresented: $vm.showEmailOtpSheet) {
      otpSheet
    }
  }

  // MARK: - Progress Bar

  private var progressBar: some View {
    VStack(spacing: 8) {
      HStack {
        if vm.currentStep.rawValue > 0 {
          Button { vm.back() } label: {
            Image(systemName: "chevron.left")
              .font(.system(size: 14, weight: .medium))
              .foregroundColor(.black)
          }
        }

        Spacer()

        Text("\(vm.currentStep.rawValue + 1) of \(vm.totalSteps)")
          .font(.system(size: 11))
          .foregroundColor(.gray)
      }
      .padding(.horizontal, 20)

      GeometryReader { geo in
        ZStack(alignment: .leading) {
          RoundedRectangle(cornerRadius: 2)
            .fill(Color(.systemGray6))
            .frame(height: 3)

          RoundedRectangle(cornerRadius: 2)
            .fill(Color.black)
            .frame(width: geo.size.width * vm.progress, height: 3)
            .animation(.easeInOut(duration: 0.3), value: vm.progress)
        }
      }
      .frame(height: 3)
      .padding(.horizontal, 20)
    }
    .padding(.top, 16)
    .padding(.bottom, 8)
  }

  // MARK: - Step Content

  @ViewBuilder
  private var stepContent: some View {
    switch vm.currentStep {
    case .name: nameStep
    case .goal: goalStep
    case .email: emailStep
    case .budget: budgetStep
    case .difficulty: difficultyStep
    case .frequency: frequencyStep
    case .pool: poolStep
    case .friends: friendsStep
    case .wallet: walletStep
    }
  }

  // MARK: - Name Step

  private var nameStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "What's your name?", subtitle: "This is how other agents will know you")

      TextField("First name", text: $vm.firstName)
        .font(.system(size: 16))
        .padding(14)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
  }

  // MARK: - Goal Step

  private var goalStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "What's your goal?", subtitle: "Tell us what you want to achieve with OpenDND")

      TextField("e.g. Explore my city, meet new people, have fun...", text: $vm.generalGoal, axis: .vertical)
        .font(.system(size: 14))
        .lineLimit(3...6)
        .padding(14)
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
  }

  // MARK: - Email Step

  private var emailStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Verify your email", subtitle: "We'll use Dynamic to secure your account")

      if vm.emailVerified {
        HStack(spacing: 10) {
          ZStack {
            Circle()
              .fill(Color.black)
              .frame(width: 32, height: 32)
            Image(systemName: "checkmark")
              .font(.system(size: 14, weight: .bold))
              .foregroundColor(.white)
          }
          VStack(alignment: .leading, spacing: 2) {
            Text("Email verified")
              .font(.system(size: 14, weight: .medium))
            Text(vm.email)
              .font(.system(size: 12))
              .foregroundColor(.gray)
          }
          Spacer()
        }
        .padding(14)
        .background(Color(.systemGray6))
        .cornerRadius(10)
      } else {
        TextField("Enter email", text: $vm.email)
          .font(.system(size: 14))
          .padding(14)
          .background(Color(.systemGray6))
          .cornerRadius(10)
          .autocapitalization(.none)
          .keyboardType(.emailAddress)

        Button {
          vm.sendEmailOTP()
        } label: {
          HStack(spacing: 6) {
            if vm.isLoading {
              ProgressView().scaleEffect(0.8).tint(.white)
            }
            Text("Send verification code")
              .font(.system(size: 14, weight: .medium))
          }
          .foregroundColor(.white)
          .frame(maxWidth: .infinity)
          .frame(height: 44)
          .background(vm.email.isEmpty ? Color(.systemGray4) : Color.black)
          .cornerRadius(10)
        }
        .disabled(vm.email.isEmpty || vm.isLoading)
      }

      if let error = vm.errorMessage {
        Text(error)
          .font(.system(size: 11))
          .foregroundColor(.red)
      }
    }
  }

  // MARK: - Budget Step

  private var budgetStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Quest budget", subtitle: "How much are you willing to spend per quest?")

      VStack(spacing: 8) {
        Text("$\(Int(vm.questBudget))")
          .font(.system(size: 34, weight: .semibold))
          .frame(maxWidth: .infinity)

        Slider(value: $vm.questBudget, in: 1...100, step: 1)
          .tint(.black)

        HStack {
          Text("$1").font(.system(size: 11)).foregroundColor(.gray)
          Spacer()
          Text("$100").font(.system(size: 11)).foregroundColor(.gray)
        }
      }
      .padding(20)
      .background(Color(.systemGray6))
      .cornerRadius(12)
    }
  }

  // MARK: - Difficulty Step

  private var difficultyStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Difficulty level", subtitle: "Choose how challenging your quests should be")

      VStack(spacing: 6) {
        ForEach(0..<vm.difficultyOptions.count, id: \.self) { i in
          optionRow(
            label: vm.difficultyOptions[i],
            subtitle: difficultyDesc(i),
            icon: difficultyIcon(i),
            selected: vm.difficulty == i
          ) {
            vm.difficulty = i
          }
        }
      }
    }
  }

  // MARK: - Frequency Step

  private var frequencyStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Quest frequency", subtitle: "How often do you want to receive quests?")

      VStack(spacing: 6) {
        ForEach(0..<vm.frequencyOptions.count, id: \.self) { i in
          optionRow(
            label: vm.frequencyOptions[i],
            subtitle: frequencyDesc(i),
            icon: frequencyIcon(i),
            selected: vm.frequency == i
          ) {
            vm.frequency = i
          }
        }
      }
    }
  }

  // MARK: - Pool Step

  private var poolStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Pool contribution", subtitle: "How much HBAR do you want to put in the shared pool?")

      VStack(spacing: 8) {
        HStack(spacing: 4) {
          Text("$\(Int(vm.poolAmount))")
            .font(.system(size: 34, weight: .semibold))
          Text("HBAR")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(.gray)
            .padding(.top, 10)
        }
        .frame(maxWidth: .infinity)

        Slider(value: $vm.poolAmount, in: 10...500, step: 5)
          .tint(.black)

        HStack {
          Text("$10").font(.system(size: 11)).foregroundColor(.gray)
          Spacer()
          Text("$500").font(.system(size: 11)).foregroundColor(.gray)
        }
      }
      .padding(20)
      .background(Color(.systemGray6))
      .cornerRadius(12)

      HStack(spacing: 8) {
        Image(systemName: "info.circle")
          .font(.system(size: 12))
        Text("This goes into the Hedera pool. You earn rewards when you complete quests.")
          .font(.system(size: 11))
      }
      .foregroundColor(.gray)
    }
  }

  // MARK: - Friends Step

  private var friendsStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Play with friends", subtitle: "Invite friends or join an existing group")

      // Segmented control
      HStack(spacing: 0) {
        segmentButton(label: "Create Group", selected: vm.groupMode == 0) { vm.groupMode = 0 }
        segmentButton(label: "Join Group", selected: vm.groupMode == 1) { vm.groupMode = 1 }
      }
      .background(Color(.systemGray6))
      .cornerRadius(10)

      if vm.groupMode == 0 {
        // Create group: add friends by phone
        VStack(spacing: 8) {
          ForEach(Array(vm.friends.enumerated()), id: \.element.id) { index, _ in
            HStack(spacing: 8) {
              TextField("Phone number", text: $vm.friends[index].phone)
                .font(.system(size: 14))
                .padding(12)
                .background(Color(.systemGray6))
                .cornerRadius(10)
                .keyboardType(.phonePad)

              if vm.friends.count > 1 {
                Button {
                  vm.removeFriend(at: index)
                } label: {
                  Image(systemName: "minus.circle")
                    .font(.system(size: 18))
                    .foregroundColor(.gray)
                }
              }
            }
          }

          Button {
            vm.addFriend()
          } label: {
            HStack(spacing: 6) {
              Image(systemName: "plus.circle")
                .font(.system(size: 14))
              Text("Add another friend")
                .font(.system(size: 13, weight: .medium))
            }
            .foregroundColor(.black)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .overlay(
              RoundedRectangle(cornerRadius: 8)
                .stroke(Color(.systemGray4), lineWidth: 0.5)
            )
          }
        }
      } else {
        // Join group: enter group name
        TextField("Enter group name", text: $vm.groupName)
          .font(.system(size: 14))
          .padding(14)
          .background(Color(.systemGray6))
          .cornerRadius(10)
      }
    }
  }

  // MARK: - Wallet Step

  private var walletStep: some View {
    VStack(alignment: .leading, spacing: 12) {
      stepHeader(title: "Create your wallet", subtitle: "An embedded wallet to hold your quest rewards")

      if vm.walletCreated {
        HStack(spacing: 10) {
          ZStack {
            Circle()
              .fill(Color.black)
              .frame(width: 40, height: 40)
            Image(systemName: "checkmark")
              .font(.system(size: 16, weight: .bold))
              .foregroundColor(.white)
          }

          VStack(alignment: .leading, spacing: 2) {
            Text("Wallet created")
              .font(.system(size: 14, weight: .medium))
            Text("Your EVM wallet is ready")
              .font(.system(size: 12))
              .foregroundColor(.gray)
          }

          Spacer()
        }
        .padding(16)
        .background(Color(.systemGray6))
        .cornerRadius(12)
        .overlay(
          RoundedRectangle(cornerRadius: 12)
            .stroke(Color(.systemGray5), lineWidth: 0.5)
        )
      } else {
        VStack(spacing: 16) {
          ZStack {
            Circle()
              .fill(Color(.systemGray6))
              .frame(width: 56, height: 56)
            Image(systemName: "wallet.pass")
              .font(.system(size: 22))
              .foregroundColor(.black)
          }

          Text("We'll create a secure embedded wallet powered by Dynamic")
            .font(.system(size: 13))
            .foregroundColor(.gray)
            .multilineTextAlignment(.center)

          Button {
            Task { await vm.createWallet() }
          } label: {
            HStack(spacing: 6) {
              if vm.isCreatingWallet {
                ProgressView().scaleEffect(0.8).tint(.white)
              } else {
                Image(systemName: "plus.circle")
                  .font(.system(size: 14))
              }
              Text(vm.isCreatingWallet ? "Creating..." : "Create Wallet")
                .font(.system(size: 14, weight: .medium))
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .background(Color.black)
            .cornerRadius(12)
          }
          .disabled(vm.isCreatingWallet)

          // Divider
          HStack {
            Rectangle().fill(Color(.systemGray5)).frame(height: 0.5)
            Text("or")
              .font(.system(size: 11))
              .foregroundColor(.gray)
              .padding(.horizontal, 8)
            Rectangle().fill(Color(.systemGray5)).frame(height: 0.5)
          }

          Button {
            vm.openDynamicAuth()
          } label: {
            HStack(spacing: 8) {
              Image(systemName: "person.circle")
                .font(.system(size: 16))
              Text("Set up via Dynamic")
                .font(.system(size: 14, weight: .medium))
            }
            .foregroundColor(.black)
            .frame(maxWidth: .infinity)
            .frame(height: 44)
            .overlay(
              RoundedRectangle(cornerRadius: 10)
                .stroke(Color(.systemGray4), lineWidth: 0.5)
            )
          }
        }
        .padding(20)
        .background(Color(.systemGray6).opacity(0.5))
        .cornerRadius(12)
        .overlay(
          RoundedRectangle(cornerRadius: 12)
            .stroke(Color(.systemGray5), lineWidth: 0.5)
        )
      }

      if let error = vm.errorMessage {
        Text(error)
          .font(.system(size: 11))
          .foregroundColor(.red)
      }
    }
    .onAppear { vm.checkExistingWallet() }
  }

  // MARK: - OTP Sheet

  private var otpSheet: some View {
    VStack(spacing: 20) {
      Text("Verify Email")
        .font(.system(size: 17, weight: .semibold))

      Text("Enter the code sent to \(vm.email)")
        .font(.system(size: 13))
        .foregroundColor(.gray)

      TextField("000000", text: $vm.otpCode)
        .font(.system(size: 20, weight: .medium, design: .monospaced))
        .multilineTextAlignment(.center)
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
        .keyboardType(.numberPad)

      Button {
        Task { await vm.verifyEmailOTP() }
      } label: {
        HStack(spacing: 6) {
          if vm.isLoading {
            ProgressView().scaleEffect(0.8).tint(.white)
          }
          Text("Verify")
            .font(.system(size: 14, weight: .medium))
        }
        .foregroundColor(.white)
        .frame(maxWidth: .infinity)
        .frame(height: 44)
        .background(vm.otpCode.count >= 4 ? Color.black : Color(.systemGray4))
        .cornerRadius(10)
      }
      .disabled(vm.otpCode.count < 4 || vm.isLoading)
    }
    .padding(24)
    .presentationDetents([.height(280)])
  }

  // MARK: - Bottom Buttons

  private var bottomButtons: some View {
    VStack(spacing: 0) {
      Rectangle()
        .fill(Color(.systemGray5))
        .frame(height: 0.5)

      HStack(spacing: 10) {
        if vm.currentStep != .name {
          Button {
            vm.back()
          } label: {
            Text("Back")
              .font(.system(size: 14, weight: .medium))
              .foregroundColor(.black)
              .frame(maxWidth: .infinity)
              .frame(height: 48)
              .overlay(
                RoundedRectangle(cornerRadius: 12)
                  .stroke(Color(.systemGray4), lineWidth: 0.5)
              )
          }
        }

        Button {
          if vm.isLastStep {
            Task {
              let success = await vm.submitOnboarding()
              if success {
                onComplete()
              } else {
                // Save locally anyway so user isn't stuck
                onComplete()
              }
            }
          } else {
            vm.next()
          }
        } label: {
          HStack(spacing: 6) {
            if vm.isSaving {
              ProgressView().scaleEffect(0.8).tint(.white)
            }
            Text(vm.isLastStep ? "Start Playing" : "Continue")
              .font(.system(size: 14, weight: .medium))
          }
          .foregroundColor(.white)
          .frame(maxWidth: .infinity)
          .frame(height: 48)
          .background(vm.canContinue ? Color.black : Color(.systemGray4))
          .cornerRadius(12)
        }
        .disabled(!vm.canContinue || vm.isSaving)
      }
      .padding(.horizontal, 20)
      .padding(.vertical, 14)
    }
  }

  // MARK: - Helpers

  private func stepHeader(title: String, subtitle: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      Text(title)
        .font(.system(size: 20, weight: .semibold))
      Text(subtitle)
        .font(.system(size: 13))
        .foregroundColor(.gray)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(.bottom, 8)
  }

  private func optionRow(label: String, subtitle: String, icon: String, selected: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      HStack(spacing: 12) {
        ZStack {
          Circle()
            .fill(selected ? Color.black : Color(.systemGray6))
            .frame(width: 32, height: 32)
          Image(systemName: icon)
            .font(.system(size: 13))
            .foregroundColor(selected ? .white : .gray)
        }

        VStack(alignment: .leading, spacing: 2) {
          Text(label)
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(.black)
          Text(subtitle)
            .font(.system(size: 11))
            .foregroundColor(.gray)
        }

        Spacer()

        if selected {
          Image(systemName: "checkmark")
            .font(.system(size: 12, weight: .bold))
            .foregroundColor(.black)
        }
      }
      .padding(12)
      .background(selected ? Color(.systemGray6) : Color.white)
      .cornerRadius(10)
      .overlay(
        RoundedRectangle(cornerRadius: 10)
          .stroke(selected ? Color.black.opacity(0.2) : Color(.systemGray5), lineWidth: 0.5)
      )
    }
    .buttonStyle(.plain)
  }

  private func segmentButton(label: String, selected: Bool, action: @escaping () -> Void) -> some View {
    Button(action: action) {
      Text(label)
        .font(.system(size: 13, weight: .medium))
        .foregroundColor(selected ? .white : .black)
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(selected ? Color.black : Color.clear)
        .cornerRadius(8)
    }
    .padding(2)
  }

  private func difficultyDesc(_ i: Int) -> String {
    ["Casual & relaxed", "Some challenge", "Intense missions", "Maximum stakes"][i]
  }

  private func difficultyIcon(_ i: Int) -> String {
    ["leaf", "flame", "bolt", "exclamationmark.triangle"][i]
  }

  private func frequencyDesc(_ i: Int) -> String {
    ["A new quest every day", "One quest per week", "Every two weeks", "Once a month"][i]
  }

  private func frequencyIcon(_ i: Int) -> String {
    ["sun.max", "calendar", "calendar.badge.clock", "moon.stars"][i]
  }
}
