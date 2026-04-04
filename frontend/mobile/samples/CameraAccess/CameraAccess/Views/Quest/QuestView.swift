/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct QuestView: View {
  @StateObject private var vm = QuestViewModel()
  @State private var expandedStep: Int? = nil

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        if vm.isLoading {
          ProgressView()
            .padding(.top, 80)
        } else if vm.hasNoQuest {
          noQuestView
        } else if let quest = vm.quest {
          headerSection(quest: quest)
          stepsSection(steps: quest.steps)
          actionLogSection(actions: quest.actions)
          ctaSection
        }
      }
    }
    .background(Color.white)
    .onAppear { vm.load() }
  }

  // MARK: - No Quest

  private var noQuestView: some View {
    VStack(spacing: 12) {
      Spacer().frame(height: 80)
      Image(systemName: "shield.lefthalf.filled")
        .font(.system(size: 40))
        .foregroundColor(.gray)
      Text("No Active Quest")
        .font(.system(size: 18, weight: .semibold))
      Text("Generate a quest to get started")
        .font(.system(size: 13))
        .foregroundColor(.gray)
    }
  }

  // MARK: - Header

  private func headerSection(quest: ActiveQuestResponse) -> some View {
    VStack(alignment: .leading, spacing: 4) {
      HStack {
        Text("Active Quest")
          .font(.system(size: 10, weight: .medium))
          .foregroundColor(.gray)
          .textCase(.uppercase)
          .tracking(1)

        Spacer()

        if let limit = quest.timeLimitMinutes {
          HStack(spacing: 3) {
            Image(systemName: "clock")
              .font(.system(size: 10))
            Text("\(limit)m left")
              .font(.system(size: 10))
          }
          .foregroundColor(.gray)
        }
      }

      Text(quest.title)
        .font(.system(size: 20, weight: .semibold))

      if let desc = quest.description {
        Text(desc)
          .font(.system(size: 13))
          .foregroundColor(.gray)
      }

      VStack(spacing: 4) {
        HStack {
          Text("\(quest.completedSteps) of \(quest.totalSteps) steps")
            .font(.system(size: 11))
            .foregroundColor(.gray)
          Spacer()
          Text("\(Int(quest.progress * 100))%")
            .font(.system(size: 11, weight: .medium))
        }

        GeometryReader { geometry in
          ZStack(alignment: .leading) {
            RoundedRectangle(cornerRadius: 2)
              .fill(Color(.systemGray6))
              .frame(height: 3)

            RoundedRectangle(cornerRadius: 2)
              .fill(Color.black)
              .frame(width: geometry.size.width * quest.progress, height: 3)
              .animation(.easeInOut(duration: 0.7), value: quest.progress)
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

  private func stepsSection(steps: [QuestStepResponse]) -> some View {
    VStack(spacing: 6) {
      ForEach(steps) { step in
        stepCard(step)
      }
    }
    .padding(.horizontal, 20)
    .padding(.vertical, 20)
  }

  private func stepCard(_ step: QuestStepResponse) -> some View {
    Button {
      withAnimation(.easeInOut(duration: 0.2)) {
        expandedStep = expandedStep == step.id ? nil : step.id
      }
    } label: {
      VStack(alignment: .leading, spacing: 0) {
        HStack(spacing: 10) {
          ZStack {
            Circle()
              .fill(step.done ? Color.black : Color.clear)
              .frame(width: 30, height: 30)

            if !step.done {
              Circle()
                .stroke(Color(.systemGray4), lineWidth: 1)
                .frame(width: 30, height: 30)
            }

            Image(systemName: step.done ? "checkmark" : (step.icon ?? "star"))
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

            if let subtitle = step.subtitle {
              Text(subtitle)
                .font(.system(size: 11))
                .foregroundColor(.gray)
            }
          }

          Spacer()

          Image(systemName: "chevron.right")
            .font(.system(size: 12))
            .foregroundColor(.gray)
            .rotationEffect(.degrees(expandedStep == step.id ? 90 : 0))
        }
        .padding(10)

        if expandedStep == step.id, let content = step.content {
          VStack(alignment: .leading, spacing: 0) {
            Rectangle()
              .fill(Color(.systemGray5))
              .frame(height: 0.5)
              .padding(.bottom, 10)

            Text(content)
              .font(.system(size: 11))
              .foregroundColor(.gray)
              .lineSpacing(2)
              .padding(10)
              .background(Color.white)
              .cornerRadius(8)
              .overlay(
                RoundedRectangle(cornerRadius: 8)
                  .stroke(Color(.systemGray5), lineWidth: 0.5)
              )
          }
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

  // MARK: - Action Log

  private func actionLogSection(actions: [QuestActionResponse]) -> some View {
    Group {
      if !actions.isEmpty {
        VStack(alignment: .leading, spacing: 0) {
          Text("Action Log")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
            .tracking(1)
            .padding(.bottom, 8)

          ForEach(actions) { action in
            HStack(spacing: 10) {
              Text(formatTime(action.createdAt))
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
    }
  }

  // MARK: - CTA

  private var ctaSection: some View {
    NavigationLink(destination: PostQuestView()) {
      Text("View Quest Summary")
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

  private func formatTime(_ date: Date?) -> String {
    guard let date = date else { return "--:--" }
    let f = DateFormatter()
    f.dateFormat = "HH:mm"
    return f.string(from: date)
  }
}
