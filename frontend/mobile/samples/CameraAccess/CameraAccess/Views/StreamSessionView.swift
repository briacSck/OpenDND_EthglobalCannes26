/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

//
// StreamSessionView.swift
//
//

import MWDATCore
import SwiftUI

struct StreamSessionView: View {
  let wearables: WearablesInterface
  @ObservedObject private var wearablesViewModel: WearablesViewModel
  @StateObject private var viewModel: StreamSessionViewModel
  @StateObject private var questVM = QuestCameraViewModel()

  init(wearables: WearablesInterface, wearablesVM: WearablesViewModel) {
    self.wearables = wearables
    self.wearablesViewModel = wearablesVM
    self._viewModel = StateObject(wrappedValue: StreamSessionViewModel(wearables: wearables))
  }

  var body: some View {
    ZStack {
      if viewModel.streamingStatus == .streaming, viewModel.hasReceivedFirstFrame {
        // Ray-Ban stream is live
        StreamView(viewModel: viewModel, wearablesVM: wearablesViewModel)

        // Quest overlay on top of Ray-Ban stream
        QuestCameraOverlayView(
          vm: questVM,
          onCapture: {
            viewModel.capturePhoto()
          },
          rayBanPhoto: viewModel.capturedPhoto
        )
      } else {
        // Waiting for Ray-Ban glasses
        waitingForGlassesView
      }
    }
    .alert("Error", isPresented: $viewModel.showError) {
      Button("OK") {
        viewModel.dismissError()
      }
    } message: {
      Text(viewModel.errorMessage)
    }
    .onChange(of: viewModel.hasActiveDevice) { hasDevice in
      if hasDevice && !viewModel.isStreaming {
        Task { await viewModel.handleStartStreaming() }
      }
    }
    .onAppear {
      questVM.load()
      if viewModel.hasActiveDevice && !viewModel.isStreaming {
        Task { await viewModel.handleStartStreaming() }
      }
    }
    .onChange(of: viewModel.capturedPhoto) { photo in
      if let photo = photo {
        questVM.verifyWithRayBanPhoto(photo)
        viewModel.dismissPhotoPreview()
      }
    }
  }

  // MARK: - Waiting for Glasses

  private var waitingForGlassesView: some View {
    ZStack {
      Color.black.edgesIgnoringSafeArea(.all)

      VStack(spacing: 24) {
        Spacer()

        Image(systemName: "eyeglasses")
          .font(.system(size: 64))
          .foregroundColor(.white.opacity(0.6))

        Text("Waiting for Ray-Ban Meta...")
          .font(.system(size: 20, weight: .semibold))
          .foregroundColor(.white)

        if viewModel.streamingStatus == .waiting {
          HStack(spacing: 12) {
            ProgressView()
              .tint(.white)
            Text("Connecting...")
              .font(.system(size: 14))
              .foregroundColor(.white.opacity(0.7))
          }
        } else {
          Text("Open Meta AI app and connect your glasses")
            .font(.system(size: 14))
            .foregroundColor(.white.opacity(0.5))
            .multilineTextAlignment(.center)
            .padding(.horizontal, 40)
        }

        Button {
          Task { await viewModel.handleStartStreaming() }
        } label: {
          Text("Retry Connection")
            .font(.system(size: 14, weight: .medium))
            .foregroundColor(.black)
            .frame(width: 180, height: 44)
            .background(Color.white)
            .cornerRadius(12)
        }

        Spacer()
      }
    }
  }
}
