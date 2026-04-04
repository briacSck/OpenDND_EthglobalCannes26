import Foundation
import SwiftUI

@MainActor
final class QuestViewModel: ObservableObject {
  @Published var quest: ActiveQuestResponse?
  @Published var isLoading = false
  @Published var errorMessage: String?
  @Published var hasNoQuest = false

  private let api = APIService.shared

  func load() {
    guard let userId = api.currentUserId else {
      hasNoQuest = true
      return
    }
    isLoading = true
    errorMessage = nil

    Task {
      do {
        let result = try await api.fetchActiveQuest(userId: userId)
        quest = result
        hasNoQuest = result == nil
      } catch {
        errorMessage = error.localizedDescription
        hasNoQuest = true
      }
      isLoading = false
    }
  }
}
