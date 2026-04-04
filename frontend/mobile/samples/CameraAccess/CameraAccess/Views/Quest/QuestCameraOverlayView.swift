import SwiftUI

struct QuestCameraOverlayView: View {
  @ObservedObject var vm: QuestCameraViewModel
  var onCapture: () -> Void  // Trigger photo capture (Ray-Ban or phone)
  var rayBanPhoto: UIImage?  // Latest Ray-Ban captured photo

  var body: some View {
    ZStack {
      // Top: Current step info
      VStack {
        if let step = vm.currentStep {
          stepOverlay(step)
        } else if vm.questCompleted {
          questCompletedBanner
        } else if vm.quest == nil {
          noQuestBanner
        }

        Spacer()

        // Bottom: Capture controls
        if vm.currentStep != nil {
          bottomControls
        }
      }

      // Verification loading overlay
      if vm.isVerifying {
        verifyingOverlay
      }

      // Result overlay
      if vm.showResult, let result = vm.verificationResult {
        resultOverlay(result)
      }
    }
    .onAppear { vm.load() }
  }

  // MARK: - Step Overlay

  private func stepOverlay(_ step: QuestStepResponse) -> some View {
    VStack(alignment: .leading, spacing: 6) {
      // Progress
      if let quest = vm.quest {
        HStack {
          Text("Step \(step.stepOrder)/\(quest.totalSteps)")
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .foregroundColor(.white.opacity(0.8))

          Spacer()

          Text("\(vm.totalXP) XP")
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .foregroundColor(.yellow)
        }

        // Progress bar
        GeometryReader { geo in
          ZStack(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2)
              .fill(Color.white.opacity(0.2))
              .frame(height: 3)
            RoundedRectangle(cornerRadius: 2)
              .fill(Color.white)
              .frame(width: geo.size.width * quest.progress, height: 3)
          }
        }
        .frame(height: 3)
      }

      // Step title
      Text(step.title)
        .font(.system(size: 16, weight: .bold))
        .foregroundColor(.white)

      // Player action (what to do)
      if let action = step.playerAction, !action.isEmpty {
        HStack(alignment: .top, spacing: 8) {
          Image(systemName: "camera.viewfinder")
            .font(.system(size: 14))
            .foregroundColor(.yellow)
          Text(action)
            .font(.system(size: 13))
            .foregroundColor(.white.opacity(0.9))
            .lineLimit(3)
        }
      } else if let content = step.content, !content.isEmpty {
        Text(content)
          .font(.system(size: 12))
          .foregroundColor(.white.opacity(0.8))
          .lineLimit(2)
      }
    }
    .padding(16)
    .background(
      LinearGradient(
        gradient: Gradient(colors: [Color.black.opacity(0.85), Color.black.opacity(0.4), Color.clear]),
        startPoint: .top,
        endPoint: .bottom
      )
    )
  }

  // MARK: - Bottom Controls

  private var bottomControls: some View {
    VStack(spacing: 12) {
      // Camera prompt hint
      if let step = vm.currentStep, let prompt = step.cameraPrompt, !prompt.isEmpty {
        Text(prompt)
          .font(.system(size: 11))
          .foregroundColor(.white.opacity(0.7))
          .multilineTextAlignment(.center)
          .lineLimit(2)
          .padding(.horizontal, 40)
      }

      HStack(spacing: 40) {
        // Skip button
        Button {
          vm.skipStep()
        } label: {
          VStack(spacing: 4) {
            Image(systemName: "forward.fill")
              .font(.system(size: 18))
            Text("Skip")
              .font(.system(size: 10))
          }
          .foregroundColor(.white.opacity(0.6))
        }

        // Main capture button
        Button(action: onCapture) {
          ZStack {
            Circle()
              .stroke(Color.white, lineWidth: 4)
              .frame(width: 72, height: 72)
            Circle()
              .fill(Color.white)
              .frame(width: 60, height: 60)
            Image(systemName: "camera.fill")
              .font(.system(size: 24))
              .foregroundColor(.black)
          }
        }

        // Phone camera fallback
        Button {
          vm.showPhoneCameraCapture = true
        } label: {
          VStack(spacing: 4) {
            Image(systemName: "iphone.camera")
              .font(.system(size: 18))
            Text("Phone")
              .font(.system(size: 10))
          }
          .foregroundColor(.white.opacity(0.6))
        }
      }
    }
    .padding(.bottom, 40)
    .background(
      LinearGradient(
        gradient: Gradient(colors: [Color.clear, Color.black.opacity(0.4), Color.black.opacity(0.85)]),
        startPoint: .top,
        endPoint: .bottom
      )
    )
  }

  // MARK: - Verifying Overlay

  private var verifyingOverlay: some View {
    ZStack {
      Color.black.opacity(0.7)
        .edgesIgnoringSafeArea(.all)

      VStack(spacing: 16) {
        ProgressView()
          .scaleEffect(1.5)
          .tint(.white)
        Text("Analyzing photo...")
          .font(.system(size: 16, weight: .medium))
          .foregroundColor(.white)
        Text("Claude Vision is checking your step")
          .font(.system(size: 12))
          .foregroundColor(.white.opacity(0.6))
      }
    }
  }

  // MARK: - Result Overlay

  private func resultOverlay(_ result: VerifyStepResponse) -> some View {
    ZStack {
      Color.black.opacity(0.8)
        .edgesIgnoringSafeArea(.all)
        .onTapGesture { vm.dismissResult() }

      VStack(spacing: 20) {
        // Icon
        ZStack {
          Circle()
            .fill(result.validated ? Color.green.opacity(0.2) : Color.orange.opacity(0.2))
            .frame(width: 80, height: 80)
          Image(systemName: result.validated ? "checkmark.circle.fill" : "arrow.clockwise.circle.fill")
            .font(.system(size: 44))
            .foregroundColor(result.validated ? .green : .orange)
        }

        // Status
        Text(result.validated ? "Step Validated!" : "Try Again")
          .font(.system(size: 22, weight: .bold))
          .foregroundColor(.white)

        // XP
        if result.validated && result.xpEarned > 0 {
          Text("+\(result.xpEarned) XP")
            .font(.system(size: 18, weight: .bold, design: .monospaced))
            .foregroundColor(.yellow)
        }

        // Narrative reaction
        if !result.narrativeReaction.isEmpty {
          Text(result.narrativeReaction)
            .font(.system(size: 14))
            .foregroundColor(.white.opacity(0.9))
            .multilineTextAlignment(.center)
            .padding(.horizontal, 30)
        }

        // Details
        if !result.details.isEmpty {
          Text(result.details)
            .font(.system(size: 11))
            .foregroundColor(.white.opacity(0.5))
            .multilineTextAlignment(.center)
            .padding(.horizontal, 30)
        }

        // Continue button
        Button {
          vm.dismissResult()
        } label: {
          Text(result.validated ? "Continue" : "Try Again")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(.black)
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .background(Color.white)
            .cornerRadius(12)
        }
        .padding(.horizontal, 40)
        .padding(.top, 8)
      }
    }
  }

  // MARK: - No Quest / Completed

  private var noQuestBanner: some View {
    VStack(spacing: 8) {
      Text("No Active Quest")
        .font(.system(size: 16, weight: .semibold))
        .foregroundColor(.white)
      Text("Generate a quest in the Quest tab first")
        .font(.system(size: 12))
        .foregroundColor(.white.opacity(0.6))
    }
    .padding(20)
    .background(Color.black.opacity(0.7))
    .cornerRadius(16)
    .padding(.top, 60)
  }

  private var questCompletedBanner: some View {
    VStack(spacing: 12) {
      Image(systemName: "trophy.fill")
        .font(.system(size: 40))
        .foregroundColor(.yellow)
      Text("Quest Complete!")
        .font(.system(size: 20, weight: .bold))
        .foregroundColor(.white)
      Text("Total XP: \(vm.totalXP)")
        .font(.system(size: 16, weight: .medium, design: .monospaced))
        .foregroundColor(.yellow)
    }
    .padding(24)
    .background(Color.black.opacity(0.8))
    .cornerRadius(20)
    .padding(.top, 60)
  }
}
