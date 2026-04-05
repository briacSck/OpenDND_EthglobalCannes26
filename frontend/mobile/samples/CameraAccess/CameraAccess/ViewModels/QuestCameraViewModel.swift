import Foundation
import SwiftUI
import AVFoundation

@MainActor
final class QuestCameraViewModel: ObservableObject {
  @Published var quest: ActiveQuestResponse?
  @Published var currentStep: QuestStepResponse?
  @Published var isVerifying = false
  @Published var verificationResult: VerifyStepResponse?
  @Published var showResult = false
  @Published var errorMessage: String?
  @Published var questCompleted = false
  @Published var totalXP = 0

  // Phone camera
  @Published var capturedImage: UIImage?
  @Published var showPhoneCameraCapture = false

  private let api = APIService.shared

  func load() {
    guard let userId = api.currentUserId else {
      print("[QuestCamera] No userId found")
      return
    }
    Task {
      do {
        let result = try await api.fetchActiveQuest(userId: userId)
        quest = result
        currentStep = result?.steps.first(where: { $0.active })
        print("[QuestCamera] Loaded quest: \(result?.title ?? "none"), activeStep: \(currentStep?.title ?? "none")")
      } catch {
        print("[QuestCamera] Load error: \(error)")
        errorMessage = error.localizedDescription
      }
    }
  }

  func verifyWithImage(_ image: UIImage) {
    print("[QuestCamera] verifyWithImage called, quest=\(quest?.title ?? "nil"), step=\(currentStep?.title ?? "nil")")
    guard let quest = quest, let step = currentStep else {
      print("[QuestCamera] No quest or step — skipping verification")
      return
    }
    isVerifying = true
    errorMessage = nil

    Task {
      do {
        print("[QuestCamera] Sending to verify API: quest=\(quest.id) step=\(step.stepOrder)")
        let result = try await api.verifyStep(
          questId: quest.id,
          stepOrder: step.stepOrder,
          image: image,
          step: step
        )
        print("[QuestCamera] Result: validated=\(result.validated), xp=\(result.xpEarned)")
        verificationResult = result
        showResult = true
        isVerifying = false

        if result.validated {
          totalXP += result.xpEarned
          try? await Task.sleep(nanoseconds: 500_000_000)
          await reloadQuest()
        }
      } catch {
        print("[QuestCamera] Verify error: \(error)")
        errorMessage = "Verification failed: \(error.localizedDescription)"
        isVerifying = false
      }
    }
  }

  /// Verify using the Meta Ray-Ban captured photo
  func verifyWithRayBanPhoto(_ photo: UIImage) {
    verifyWithImage(photo)
  }

  func dismissResult() {
    showResult = false
    verificationResult = nil
    capturedImage = nil
  }

  func skipStep() {
    guard let quest = quest, let step = currentStep else { return }
    Task {
      do {
        try await api.markStepDone(questId: quest.id, stepOrder: step.stepOrder)
        try? await Task.sleep(nanoseconds: 300_000_000)
        await reloadQuest()
      } catch {
        errorMessage = "Failed to skip: \(error.localizedDescription)"
      }
    }
  }

  private func reloadQuest() async {
    guard let userId = api.currentUserId else { return }
    do {
      let result = try await api.fetchActiveQuest(userId: userId)
      quest = result
      let nextActive = result?.steps.first(where: { $0.active })
      currentStep = nextActive

      // Check if quest is completed (no more active steps, all done)
      if nextActive == nil, let q = result, q.completedSteps == q.totalSteps {
        questCompleted = true
        try? await api.completeQuest(
          questId: q.id,
          xpEarned: totalXP,
          durationMinutes: 60
        )
      }
    } catch {
      errorMessage = error.localizedDescription
    }
  }
}

// MARK: - Phone Camera Coordinator

class PhoneCameraCoordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
  let onCapture: (UIImage) -> Void

  init(onCapture: @escaping (UIImage) -> Void) {
    self.onCapture = onCapture
  }

  func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
    if let image = info[.originalImage] as? UIImage {
      onCapture(image)
    }
    picker.dismiss(animated: true)
  }

  func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
    picker.dismiss(animated: true)
  }
}

struct PhoneCameraView: UIViewControllerRepresentable {
  let onCapture: (UIImage) -> Void

  func makeCoordinator() -> PhoneCameraCoordinator {
    PhoneCameraCoordinator(onCapture: onCapture)
  }

  func makeUIViewController(context: Context) -> UIImagePickerController {
    let picker = UIImagePickerController()
    picker.sourceType = .camera
    picker.delegate = context.coordinator
    return picker
  }

  func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}
}
