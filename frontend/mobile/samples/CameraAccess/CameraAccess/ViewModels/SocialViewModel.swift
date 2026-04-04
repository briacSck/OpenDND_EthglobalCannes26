import Foundation
import SwiftUI

@MainActor
final class SocialViewModel: ObservableObject {
  @Published var leaderboard: [LeaderboardEntryResponse] = []
  @Published var activity: [ActivityResponse] = []
  @Published var isLoading = false
  @Published var errorMessage: String?

  private let api = APIService.shared

  var currentUserId: String? { api.currentUserId }

  func load() {
    isLoading = true
    errorMessage = nil

    Task {
      do {
        async let lb = api.fetchLeaderboard()
        async let act: [ActivityResponse] = {
          if let userId = api.currentUserId {
            return try await api.fetchActivity(userId: userId)
          }
          return []
        }()

        leaderboard = try await lb
        activity = try await act
      } catch {
        errorMessage = error.localizedDescription
      }
      isLoading = false
    }
  }
}
