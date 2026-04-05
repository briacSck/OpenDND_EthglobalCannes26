import Foundation
import SwiftUI

@MainActor
final class QuestViewModel: ObservableObject {
  @Published var quest: ActiveQuestResponse?
  @Published var isLoading = false
  @Published var isGenerating = false
  @Published var errorMessage: String?
  @Published var hasNoQuest = false

  // Generate form fields
  @Published var goal = ""
  @Published var location = "Cannes, France"
  @Published var duration = 60
  @Published var difficulty = "medium"
  @Published var showGenerateSheet = false

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

  func generateQuest() {
    guard let userId = api.currentUserId else { return }
    isGenerating = true
    errorMessage = nil

    Task {
      do {
        let result = try await api.generateQuest(
          userId: userId,
          goal: goal.isEmpty ? "Explore the city and complete fun challenges" : goal,
          location: location,
          duration: duration,
          difficulty: difficulty
        )
        quest = result
        hasNoQuest = false
        showGenerateSheet = false
      } catch {
        errorMessage = "Generation failed: \(error.localizedDescription)"
      }
      isGenerating = false
    }
  }
}
