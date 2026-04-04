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
      if viewModel.isStreaming {
        // Full-screen video view with streaming controls
        StreamView(viewModel: viewModel, wearablesVM: wearablesViewModel)

        // Quest overlay on top of Ray-Ban stream
        QuestCameraOverlayView(
          vm: questVM,
          onCapture: {
            // Capture from Ray-Ban
            viewModel.capturePhoto()
          },
          rayBanPhoto: viewModel.capturedPhoto
        )
      } else {
        // Pre-streaming: show phone camera with quest overlay
        PhoneCameraPreview()
          .edgesIgnoringSafeArea(.all)

        QuestCameraOverlayView(
          vm: questVM,
          onCapture: {
            // Open phone camera capture
            questVM.showPhoneCameraCapture = true
          },
          rayBanPhoto: nil
        )
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
      // Auto-start streaming when Ray-Ban glasses are detected
      if hasDevice && !viewModel.isStreaming {
        Task { await viewModel.handleStartStreaming() }
      }
    }
    .onAppear {
      // Try to start streaming if device is already available
      if viewModel.hasActiveDevice && !viewModel.isStreaming {
        Task { await viewModel.handleStartStreaming() }
      }
    }
    .onChange(of: viewModel.capturedPhoto) { photo in
      // When Ray-Ban captures a photo, send it for verification
      if let photo = photo {
        questVM.verifyWithRayBanPhoto(photo)
        viewModel.dismissPhotoPreview()
      }
    }
    .sheet(isPresented: $questVM.showPhoneCameraCapture) {
      PhoneCameraView { image in
        questVM.showPhoneCameraCapture = false
        questVM.verifyWithImage(image)
      }
    }
  }
}

// MARK: - Phone Camera Preview (live viewfinder)

struct PhoneCameraPreview: UIViewRepresentable {
  func makeUIView(context: Context) -> UIView {
    let view = UIView(frame: .zero)
    view.backgroundColor = .black

    let session = AVCaptureSession()
    session.sessionPreset = .high

    guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
          let input = try? AVCaptureDeviceInput(device: device) else {
      return view
    }

    if session.canAddInput(input) {
      session.addInput(input)
    }

    let previewLayer = AVCaptureVideoPreviewLayer(session: session)
    previewLayer.videoGravity = .resizeAspectFill
    view.layer.addSublayer(previewLayer)

    DispatchQueue.global(qos: .userInitiated).async {
      session.startRunning()
    }

    // Store session to keep it alive
    context.coordinator.session = session
    context.coordinator.previewLayer = previewLayer

    return view
  }

  func updateUIView(_ uiView: UIView, context: Context) {
    context.coordinator.previewLayer?.frame = uiView.bounds
  }

  func makeCoordinator() -> Coordinator { Coordinator() }

  class Coordinator {
    var session: AVCaptureSession?
    var previewLayer: AVCaptureVideoPreviewLayer?
  }
}

import AVFoundation
