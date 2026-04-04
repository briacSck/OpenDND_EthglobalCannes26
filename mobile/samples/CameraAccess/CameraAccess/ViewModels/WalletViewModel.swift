/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import Foundation
import SwiftUI
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
  private var authListenerId: String?

  func startListening() {
    guard let sdk else { return }

    // Check if already authenticated
    if sdk.auth.authenticatedUser != nil {
      isAuthenticated = true
      loadWallets()
      userEmail = sdk.auth.authenticatedUser?.email
    }

    // Listen for auth state changes
    authListenerId = sdk.auth.onAuthStateChange { [weak self] event in
      Task { @MainActor in
        guard let self else { return }
        switch event {
        case .authenticated:
          self.isAuthenticated = true
          self.userEmail = sdk.auth.authenticatedUser?.email
          self.loadWallets()
        case .unauthenticated:
          self.isAuthenticated = false
          self.wallets = []
          self.userEmail = nil
        default:
          break
        }
      }
    }
  }

  func stopListening() {
    if let id = authListenerId {
      sdk?.auth.removeAuthStateChangeListener(id: id)
      authListenerId = nil
    }
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
    sdk?.ui.openAuthFlow()
  }

  func createWallet(chain: EmbeddedWalletChain = .evm) async {
    guard let sdk else { return }
    isCreatingWallet = true
    errorMessage = nil

    do {
      try await sdk.wallets.createWallet(chain: chain)
      loadWallets()
    } catch {
      errorMessage = error.localizedDescription
    }
    isCreatingWallet = false
  }

  func logout() {
    sdk?.auth.logout()
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
}
