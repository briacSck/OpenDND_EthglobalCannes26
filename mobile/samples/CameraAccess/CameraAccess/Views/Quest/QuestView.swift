/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct QuestStep: Identifiable {
  let id: Int
  let type: String
  let title: String
  let subtitle: String
  let icon: String
  let done: Bool
  var active: Bool = false
}

struct ActionLogEntry: Identifiable {
  let id = UUID()
  let time: String
  let action: String
  let xp: Int
}

struct QuestView: View {
  @State private var expandedStep: Int? = 3

  private let questSteps: [QuestStep] = [
    QuestStep(id: 1, type: "document", title: "Mission Briefing", subtitle: "Read the intel report", icon: "doc.text", done: true),
    QuestStep(id: 2, type: "video", title: "Surveillance Footage", subtitle: "Watch the 2min recon clip", icon: "video", done: true),
    QuestStep(id: 3, type: "conversation", title: "Interrogation with Agent K", subtitle: "3 dialogue choices remaining", icon: "message", done: false, active: true),
    QuestStep(id: 4, type: "action", title: "Infiltrate the Compound", subtitle: "Complete the stealth sequence", icon: "target", done: false),
    QuestStep(id: 5, type: "action", title: "Extract the Package", subtitle: "Final objective", icon: "star", done: false),
  ]

  private let previousActions: [ActionLogEntry] = [
    ActionLogEntry(time: "14:32", action: "Decoded encrypted message", xp: 50),
    ActionLogEntry(time: "14:28", action: "Chose stealth approach over combat", xp: 30),
    ActionLogEntry(time: "14:15", action: "Gathered 3/3 evidence pieces", xp: 75),
  ]

  private var completedSteps: Int {
    questSteps.filter(\.done).count
  }

  private var progress: Double {
    Double(completedSteps) / Double(questSteps.count)
  }

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        // Header
        headerSection

        // Quest Steps
        stepsSection

        // Action Log
        actionLogSection

        // Post-Quest CTA
        ctaSection
      }
    }
    .background(Color.white)
  }

  // MARK: - Header

  private var headerSection: some View {
    VStack(alignment: .leading, spacing: 4) {
      HStack {
        Text("Active Quest")
          .font(.system(size: 10, weight: .medium))
          .foregroundColor(.gray)
          .textCase(.uppercase)
          .tracking(1)

        Spacer()

        HStack(spacing: 3) {
          Image(systemName: "clock")
            .font(.system(size: 10))
          Text("2h 34m left")
            .font(.system(size: 10))
        }
        .foregroundColor(.gray)
      }

      Text("Operation Nightfall")
        .font(.system(size: 20, weight: .semibold))

      Text("Infiltrate the Syndicate's HQ and retrieve classified data")
        .font(.system(size: 13))
        .foregroundColor(.gray)

      // Progress bar
      VStack(spacing: 4) {
        HStack {
          Text("\(completedSteps) of \(questSteps.count) steps")
            .font(.system(size: 11))
            .foregroundColor(.gray)
          Spacer()
          Text("\(Int(progress * 100))%")
            .font(.system(size: 11, weight: .medium))
        }

        GeometryReader { geometry in
          ZStack(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2)
              .fill(Color(.systemGray6))
              .frame(height: 3)

            RoundedRectangle(cornerRadius: 2)
              .fill(Color.black)
              .frame(width: geometry.size.width * progress, height: 3)
              .animation(.easeInOut(duration: 0.7), value: progress)
          }
        }
        .frame(height: 3)
      }
      .padding(.top, 12)
    }
    .padding(.horizontal, 20)
    .padding(.top, 16)
    .padding(.bottom, 20)
    .overlay(
      Rectangle()
        .fill(Color(.systemGray5))
        .frame(height: 0.5),
      alignment: .bottom
    )
  }

  // MARK: - Steps

  private var stepsSection: some View {
    VStack(spacing: 6) {
      ForEach(questSteps) { step in
        stepCard(step)
      }
    }
    .padding(.horizontal, 20)
    .padding(.vertical, 20)
  }

  private func stepCard(_ step: QuestStep) -> some View {
    Button {
      withAnimation(.easeInOut(duration: 0.2)) {
        expandedStep = expandedStep == step.id ? nil : step.id
      }
    } label: {
      VStack(alignment: .leading, spacing: 0) {
        HStack(spacing: 10) {
          // Circle icon
          ZStack {
            Circle()
              .fill(step.done ? Color.black : Color.clear)
              .frame(width: 30, height: 30)

            if !step.done {
              Circle()
                .stroke(Color(.systemGray4), lineWidth: 1)
                .frame(width: 30, height: 30)
            }

            Image(systemName: step.done ? "checkmark" : step.icon)
              .font(.system(size: 12, weight: step.done ? .bold : .regular))
              .foregroundColor(step.done ? .white : .gray)
          }

          VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
              Text(step.title)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(step.done ? .gray : .black)
                .strikethrough(step.done)

              if step.active {
                Text("Now")
                  .font(.system(size: 9, weight: .medium))
                  .foregroundColor(.white)
                  .padding(.horizontal, 6)
                  .padding(.vertical, 2)
                  .background(Color.black)
                  .clipShape(Capsule())
              }
            }

            Text(step.subtitle)
              .font(.system(size: 11))
              .foregroundColor(.gray)
          }

          Spacer()

          Image(systemName: "chevron.right")
            .font(.system(size: 12))
            .foregroundColor(.gray)
            .rotationEffect(.degrees(expandedStep == step.id ? 90 : 0))
        }
        .padding(10)

        // Expanded content
        if expandedStep == step.id {
          expandedContent(for: step)
            .padding(.leading, 40)
            .padding(.trailing, 10)
            .padding(.bottom, 10)
        }
      }
      .background(step.active ? Color(.systemGray6) : Color.white)
      .cornerRadius(12)
      .overlay(
        RoundedRectangle(cornerRadius: 12)
          .stroke(Color(.systemGray5), lineWidth: 0.5)
      )
    }
    .buttonStyle(.plain)
  }

  @ViewBuilder
  private func expandedContent(for step: QuestStep) -> some View {
    VStack(alignment: .leading, spacing: 0) {
      Rectangle()
        .fill(Color(.systemGray5))
        .frame(height: 0.5)
        .padding(.bottom, 10)

      switch step.type {
      case "document":
        VStack(alignment: .leading, spacing: 8) {
          Text("CLASSIFIED — Eyes Only. The Syndicate has been identified operating from a warehouse district. Intelligence suggests the data is stored on an air-gapped server in sublevel B2...")
            .font(.system(size: 11))
            .foregroundColor(.gray)
            .lineSpacing(2)

          HStack(spacing: 3) {
            Text("Read full document")
              .font(.system(size: 11, weight: .medium))
            Image(systemName: "chevron.right")
              .font(.system(size: 10))
          }
          .foregroundColor(.black)
        }
        .padding(10)
        .background(Color.white)
        .cornerRadius(8)
        .overlay(
          RoundedRectangle(cornerRadius: 8)
            .stroke(Color(.systemGray5), lineWidth: 0.5)
        )

      case "video":
        ZStack {
          RoundedRectangle(cornerRadius: 8)
            .fill(Color(.systemGray6))
            .aspectRatio(16/9, contentMode: .fit)

          Image(systemName: "play.fill")
            .font(.system(size: 24))
            .foregroundColor(.gray)

          VStack {
            Spacer()
            HStack {
              Spacer()
              Text("2:14")
                .font(.system(size: 9))
                .foregroundColor(.gray)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(Color.white.opacity(0.8))
                .cornerRadius(4)
                .padding(6)
            }
          }
        }
        .overlay(
          RoundedRectangle(cornerRadius: 8)
            .stroke(Color(.systemGray5), lineWidth: 0.5)
        )

      case "conversation":
        VStack(spacing: 6) {
          // Agent K message
          HStack(alignment: .top, spacing: 6) {
            Text("K")
              .font(.system(size: 9, weight: .medium))
              .frame(width: 22, height: 22)
              .background(Color(.systemGray6))
              .clipShape(Circle())
              .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

            Text("\"You have 3 minutes. Choose your next words carefully, agent.\"")
              .font(.system(size: 11))
              .foregroundColor(.gray)
              .padding(.horizontal, 10)
              .padding(.vertical, 6)
              .background(Color(.systemGray6))
              .cornerRadius(8)

            Spacer()
          }

          // Player message
          HStack(alignment: .top, spacing: 6) {
            Spacer()

            Text("\"I know about the shipment. Tell me about sublevel B2.\"")
              .font(.system(size: 11))
              .foregroundColor(.white)
              .padding(.horizontal, 10)
              .padding(.vertical, 6)
              .background(Color.black)
              .cornerRadius(8)

            Text("Y")
              .font(.system(size: 9, weight: .medium))
              .frame(width: 22, height: 22)
              .background(Color(.systemGray6))
              .clipShape(Circle())
              .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))
          }

          // Continue button
          Text("Continue conversation →")
            .font(.system(size: 11, weight: .medium))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .overlay(
              RoundedRectangle(cornerRadius: 8)
                .stroke(Color(.systemGray5), lineWidth: 0.5)
            )
        }

      default:
        Text(step.active ? "Available now" : "Unlocks after previous step")
          .font(.system(size: 11))
          .foregroundColor(.gray)
      }
    }
  }

  // MARK: - Action Log

  private var actionLogSection: some View {
    VStack(alignment: .leading, spacing: 0) {
      Text("Action Log")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(1)
        .padding(.bottom, 8)

      ForEach(previousActions) { action in
        HStack(spacing: 10) {
          Text(action.time)
            .font(.system(size: 11, design: .monospaced))
            .foregroundColor(.gray)
            .frame(width: 36, alignment: .leading)

          Text(action.action)
            .font(.system(size: 11))
            .frame(maxWidth: .infinity, alignment: .leading)

          Text("+\(action.xp)")
            .font(.system(size: 11, weight: .medium))
            .foregroundColor(.gray)
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
    .padding(.horizontal, 20)
    .padding(.bottom, 20)
  }

  // MARK: - CTA

  private var ctaSection: some View {
    NavigationLink(destination: PostQuestView()) {
      Text("View Quest Summary →")
        .font(.system(size: 14, weight: .medium))
        .foregroundColor(.white)
        .frame(maxWidth: .infinity)
        .frame(height: 48)
        .background(Color.black)
        .cornerRadius(12)
    }
    .padding(.horizontal, 20)
    .padding(.bottom, 24)
  }
}
