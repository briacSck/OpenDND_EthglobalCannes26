import Foundation
import SwiftUI

@MainActor
final class HistoryViewModel: ObservableObject {
  @Published var completedQuests: [CompletedQuestResponse] = []
  @Published var badges: [BadgeResponse] = []
  @Published var personalityTraits: [PersonalityTraitResponse] = []
  @Published var user: UserResponse?
  @Published var isLoading = false
  @Published var errorMessage: String?

  private let api = APIService.shared

  var questCount: Int { completedQuests.count }
  var userLevel: Int { user?.level ?? 1 }
  var unlockedBadgeCount: Int { badges.filter(\.unlocked).count }

  func load() {
    guard let userId = api.currentUserId else { return }
    isLoading = true
    errorMessage = nil

    Task {
      do {
        async let q = api.fetchQuestHistory(userId: userId)
        async let b = api.fetchBadges(userId: userId)
        async let p = api.fetchPersonality(userId: userId)
        async let u = api.fetchUser(userId: userId)

        completedQuests = try await q
        badges = try await b
        personalityTraits = try await p
        user = try await u
      } catch {
        errorMessage = error.localizedDescription
      }
      isLoading = false
    }
  }
}
