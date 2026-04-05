/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI
import DynamicSDKSwift

struct WalletView: View {
  @StateObject private var vm = WalletViewModel()
  @State private var otpCode = ""
  @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = true

  @State private var walletData: WalletResponse?
  @State private var isLoadingWallet = false

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        if vm.isAuthenticated {
          authenticatedContent
        } else {
          connectWalletSection
        }
      }
    }
    .background(Color.white)
    .onAppear {
      vm.startListening()
      loadWallet()
    }
    .onDisappear { vm.stopListening() }
    .sheet(isPresented: $vm.showEmailOtpSheet) {
      otpSheet
    }
  }

  private func loadWallet() {
    guard let userId = APIService.shared.currentUserId else { return }
    isLoadingWallet = true
    Task {
      do {
        walletData = try await APIService.shared.fetchWallet(userId: userId)
      } catch {
        NSLog("[Wallet] Error: \(error)")
      }
      isLoadingWallet = false
    }
  }

  // MARK: - Connect Wallet (Not Authenticated)

  private var connectWalletSection: some View {
    VStack(spacing: 0) {
      VStack(spacing: 8) {
        ZStack {
          Circle()
            .fill(Color(.systemGray6))
            .frame(width: 56, height: 56)
            .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

          Image(systemName: "wallet.pass")
            .font(.system(size: 22))
            .foregroundColor(.black)
        }
        .padding(.top, 40)

        Text("Connect Wallet")
          .font(.system(size: 20, weight: .semibold))

        Text("Sign in to manage your quest earnings and on-chain assets")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .multilineTextAlignment(.center)
          .padding(.horizontal, 40)
      }
      .padding(.bottom, 28)

      VStack(spacing: 10) {
        TextField("Enter email", text: $vm.email)
          .font(.system(size: 14))
          .padding(12)
          .background(Color(.systemGray6))
          .cornerRadius(10)
          .autocapitalization(.none)
          .keyboardType(.emailAddress)

        Button {
          vm.sendEmailOTP()
        } label: {
          HStack(spacing: 6) {
            if vm.isLoading {
              ProgressView()
                .scaleEffect(0.8)
                .tint(.white)
            }
            Text("Continue with Email")
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
      .padding(.horizontal, 20)
      .padding(.bottom, 12)

      HStack {
        Rectangle().fill(Color(.systemGray5)).frame(height: 0.5)
        Text("or")
          .font(.system(size: 11))
          .foregroundColor(.gray)
          .padding(.horizontal, 8)
        Rectangle().fill(Color(.systemGray5)).frame(height: 0.5)
      }
      .padding(.horizontal, 20)
      .padding(.vertical, 12)

      Button {
        vm.openAuthFlow()
      } label: {
        HStack(spacing: 8) {
          Image(systemName: "person.circle")
            .font(.system(size: 16))
          Text("Sign in with Dynamic")
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
      .padding(.horizontal, 20)
      .padding(.bottom, 20)

      if let error = vm.errorMessage {
        Text(error)
          .font(.system(size: 11))
          .foregroundColor(.red)
          .padding(.horizontal, 20)
          .padding(.bottom, 12)
      }
    }
  }

  // MARK: - Authenticated Content

  private var authenticatedContent: some View {
    VStack(spacing: 0) {
      // Wallet header
      VStack(alignment: .leading, spacing: 4) {
        HStack {
          Text("Available Balance")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
            .tracking(1)

          Spacer()

          VStack(alignment: .trailing, spacing: 2) {
            if let hederaId = walletData?.hederaAccountId {
              HStack(spacing: 3) {
                Image(systemName: "link")
                  .font(.system(size: 8))
                Text(hederaId)
                  .font(.system(size: 10, design: .monospaced))
              }
              .foregroundColor(.black)
              .padding(.horizontal, 8)
              .padding(.vertical, 3)
              .background(Color(.systemGray6))
              .cornerRadius(6)
            }
            if !vm.truncatedAddress.isEmpty {
              Text(vm.truncatedAddress)
                .font(.system(size: 9, design: .monospaced))
                .foregroundColor(.gray)
            }
          }
        }

        if isLoadingWallet {
          ProgressView().padding(.vertical, 8)
        } else {
          Text("$\(String(format: "%.2f", walletData?.available ?? 0))")
            .font(.system(size: 34, weight: .semibold))
            .tracking(-0.5)
        }
      }
      .frame(maxWidth: .infinity, alignment: .leading)
      .padding(.horizontal, 20)
      .padding(.top, 16)
      .padding(.bottom, 20)
      .overlay(
        Rectangle()
          .fill(Color(.systemGray5))
          .frame(height: 0.5),
        alignment: .bottom
      )

      // Hedera account
      if let hederaId = walletData?.hederaAccountId {
        VStack(alignment: .leading, spacing: 6) {
          Text("Hedera Account")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
            .tracking(1)

          HStack(spacing: 10) {
            ZStack {
              Circle()
                .fill(Color(.systemGray6))
                .frame(width: 32, height: 32)
              Text("H")
                .font(.system(size: 14, weight: .bold))
            }

            VStack(alignment: .leading, spacing: 1) {
              Text(hederaId)
                .font(.system(size: 13, weight: .medium, design: .monospaced))
              Text("Hedera Testnet")
                .font(.system(size: 11))
                .foregroundColor(.gray)
            }

            Spacer()

            Button {
              UIPasteboard.general.string = hederaId
            } label: {
              Image(systemName: "doc.on.doc")
                .font(.system(size: 12))
                .foregroundColor(.gray)
            }
          }
          .padding(10)
          .background(Color(.systemGray6).opacity(0.5))
          .cornerRadius(10)
          .overlay(
            RoundedRectangle(cornerRadius: 10)
              .stroke(Color(.systemGray5), lineWidth: 0.5)
          )
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .overlay(
          Rectangle()
            .fill(Color(.systemGray5))
            .frame(height: 0.5),
          alignment: .bottom
        )
      }

      // EVM Wallets section
      if !vm.wallets.isEmpty {
        walletsSection
      } else {
        createWalletSection
      }

      // Sub-balances
      HStack(spacing: 0) {
        VStack(alignment: .leading, spacing: 4) {
          HStack(spacing: 4) {
            Image(systemName: "lock")
              .font(.system(size: 10))
            Text("Locked")
              .font(.system(size: 9, weight: .medium))
              .textCase(.uppercase)
          }
          .foregroundColor(.gray)

          Text("$\(String(format: "%.2f", walletData?.locked ?? 0))")
            .font(.system(size: 17, weight: .semibold))

          Text("Reserved for quests")
            .font(.system(size: 9))
            .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.vertical, 14)

        Rectangle()
          .fill(Color(.systemGray5))
          .frame(width: 0.5)

        VStack(alignment: .leading, spacing: 4) {
          HStack(spacing: 4) {
            Image(systemName: "clock")
              .font(.system(size: 10))
            Text("Pending")
              .font(.system(size: 9, weight: .medium))
              .textCase(.uppercase)
          }
          .foregroundColor(.gray)

          Text("$\(String(format: "%.2f", walletData?.pending ?? 0))")
            .font(.system(size: 17, weight: .semibold))

          Text("Arriving soon")
            .font(.system(size: 9))
            .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
      }
      .overlay(
        Rectangle()
          .fill(Color(.systemGray5))
          .frame(height: 0.5),
        alignment: .bottom
      )

      // Actions
      HStack(spacing: 10) {
        actionButton(icon: "arrow.down.left", label: "Deposit")
        actionButton(icon: "arrow.up.right", label: "Withdraw")
      }
      .padding(.horizontal, 20)
      .padding(.vertical, 14)

      // Transactions
      VStack(alignment: .leading, spacing: 8) {
        Text("Transactions")
          .font(.system(size: 10, weight: .medium))
          .foregroundColor(.gray)
          .textCase(.uppercase)
          .tracking(1)

        if let txs = walletData?.transactions, !txs.isEmpty {
          VStack(spacing: 0) {
            ForEach(txs) { tx in
              HStack(spacing: 10) {
                ZStack {
                  Circle()
                    .fill(Color(.systemGray6))
                    .frame(width: 28, height: 28)

                  Image(systemName: tx.type == "credit" ? "arrow.down.left" : "arrow.up.right")
                    .font(.system(size: 12))
                    .foregroundColor(tx.type == "credit" ? .black : .gray)
                }

                VStack(alignment: .leading, spacing: 1) {
                  Text(tx.label)
                    .font(.system(size: 13))
                  Text(formatDate(tx.date))
                    .font(.system(size: 11))
                    .foregroundColor(.gray)
                }

                Spacer()

                Text("\(tx.type == "credit" ? "+" : "-")$\(String(format: "%.2f", abs(tx.amount)))")
                  .font(.system(size: 13, weight: .medium))
                  .foregroundColor(tx.type == "credit" ? .black : .gray)
                  .monospacedDigit()
              }
              .padding(.vertical, 10)
              .overlay(
                Rectangle()
                  .fill(Color(.systemGray5))
                  .frame(height: 0.5),
                alignment: .bottom
              )
            }
          }
        } else {
          Text("No transactions yet")
            .font(.system(size: 13))
            .foregroundColor(.gray)
            .padding(.top, 12)
        }
      }
      .padding(.horizontal, 20)
      .padding(.bottom, 16)

      // Account actions
      VStack(spacing: 8) {
        Button {
          vm.logout()
        } label: {
          Text("Disconnect Wallet")
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(.red.opacity(0.8))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
        }

        Button {
          hasCompletedOnboarding = false
        } label: {
          Text("Restart Onboarding")
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(.gray)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
        }
      }
      .padding(.horizontal, 20)
      .padding(.bottom, 20)
    }
  }

  // MARK: - Wallets Section

  private var walletsSection: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text("Your Wallets")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(1)

      ForEach(vm.wallets, id: \.address) { wallet in
        HStack(spacing: 10) {
          ZStack {
            Circle()
              .fill(Color(.systemGray6))
              .frame(width: 32, height: 32)

            Image(systemName: "creditcard")
              .font(.system(size: 13))
          }

          VStack(alignment: .leading, spacing: 1) {
            Text(wallet.chain.uppercased())
              .font(.system(size: 12, weight: .medium))

            Text(truncateAddress(wallet.address))
              .font(.system(size: 11, design: .monospaced))
              .foregroundColor(.gray)
          }

          Spacer()

          Button {
            UIPasteboard.general.string = wallet.address
          } label: {
            Image(systemName: "doc.on.doc")
              .font(.system(size: 12))
              .foregroundColor(.gray)
          }
        }
        .padding(10)
        .background(Color(.systemGray6).opacity(0.5))
        .cornerRadius(10)
        .overlay(
          RoundedRectangle(cornerRadius: 10)
            .stroke(Color(.systemGray5), lineWidth: 0.5)
        )
      }
    }
    .padding(.horizontal, 20)
    .padding(.vertical, 14)
    .overlay(
      Rectangle()
        .fill(Color(.systemGray5))
        .frame(height: 0.5),
      alignment: .bottom
    )
  }

  // MARK: - Create Wallet

  private var createWalletSection: some View {
    Button {
      Task { await vm.createWallet() }
    } label: {
      HStack(spacing: 8) {
        if vm.isCreatingWallet {
          ProgressView()
            .scaleEffect(0.7)
            .tint(.black)
        } else {
          Image(systemName: "plus.circle")
            .font(.system(size: 14))
        }
        Text(vm.isCreatingWallet ? "Creating..." : "Create Embedded Wallet")
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
    .disabled(vm.isCreatingWallet)
    .padding(.horizontal, 20)
    .padding(.vertical, 14)
    .overlay(
      Rectangle()
        .fill(Color(.systemGray5))
        .frame(height: 0.5),
      alignment: .bottom
    )
  }

  // MARK: - OTP Sheet

  private var otpSheet: some View {
    VStack(spacing: 20) {
      Text("Verify Email")
        .font(.system(size: 17, weight: .semibold))

      Text("Enter the code sent to \(vm.email)")
        .font(.system(size: 13))
        .foregroundColor(.gray)

      TextField("000000", text: $otpCode)
        .font(.system(size: 20, weight: .medium, design: .monospaced))
        .multilineTextAlignment(.center)
        .padding(12)
        .background(Color(.systemGray6))
        .cornerRadius(10)
        .keyboardType(.numberPad)

      Button {
        Task {
          try? await vm.verifyEmailOTP(code: otpCode)
          vm.showEmailOtpSheet = false
          otpCode = ""
        }
      } label: {
        Text("Verify")
          .font(.system(size: 14, weight: .medium))
          .foregroundColor(.white)
          .frame(maxWidth: .infinity)
          .frame(height: 44)
          .background(otpCode.count >= 4 ? Color.black : Color(.systemGray4))
          .cornerRadius(10)
      }
      .disabled(otpCode.count < 4)
    }
    .padding(24)
    .presentationDetents([.height(280)])
  }

  // MARK: - Helpers

  private func actionButton(icon: String, label: String) -> some View {
    Button {
    } label: {
      HStack(spacing: 6) {
        Image(systemName: icon)
          .font(.system(size: 14))
        Text(label)
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

  private func truncateAddress(_ addr: String) -> String {
    guard addr.count > 12 else { return addr }
    return "\(addr.prefix(6))...\(addr.suffix(4))"
  }

  private func formatDate(_ date: Date?) -> String {
    guard let date = date else { return "-" }
    let f = DateFormatter()
    f.dateFormat = "MMM d"
    return f.string(from: date)
  }
}
