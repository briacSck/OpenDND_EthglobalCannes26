/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct HistoryView: View {
  @StateObject private var vm = HistoryViewModel()
  @State private var selectedTab: HistoryTab = .quests

  enum HistoryTab: String, CaseIterable {
    case quests
    case badges
    case personality
  }

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        // Header
        VStack(alignment: .leading, spacing: 2) {
          Text("History")
            .font(.system(size: 20, weight: .semibold))
          Text("\(vm.questCount) quests \u{00B7} Level \(vm.userLevel)")
            .font(.system(size: 13))
            .foregroundColor(.gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 14)
        .overlay(
          Rectangle()
            .fill(Color(.systemGray5))
            .frame(height: 0.5),
          alignment: .bottom
        )

        // Tabs
        tabSelector
          .padding(.horizontal, 20)
          .padding(.vertical, 10)

        if vm.isLoading {
          ProgressView()
            .padding(.top, 40)
        } else {
          switch selectedTab {
          case .quests:
            questsContent
          case .badges:
            badgesContent
          case .personality:
            personalityContent
          }
        }
      }
    }
    .background(Color.white)
    .onAppear { vm.load() }
  }

  // MARK: - Tab Selector

  private var tabSelector: some View {
    HStack(spacing: 3) {
      ForEach(HistoryTab.allCases, id: \.self) { tab in
        Button {
          withAnimation(.easeInOut(duration: 0.15)) {
            selectedTab = tab
          }
        } label: {
          Text(tab.rawValue.capitalized)
            .font(.system(size: 12, weight: .medium))
            .foregroundColor(selectedTab == tab ? .black : .gray)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 7)
            .background(selectedTab == tab ? Color.white : Color.clear)
            .cornerRadius(6)
            .shadow(color: selectedTab == tab ? .black.opacity(0.06) : .clear, radius: 2, y: 1)
        }
      }
    }
    .padding(2)
    .background(Color(.systemGray6))
    .cornerRadius(8)
  }

  // MARK: - Quests

  private var questsContent: some View {
    VStack(spacing: 0) {
      if vm.completedQuests.isEmpty {
        Text("No completed quests yet")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .padding(.top, 40)
      } else {
        ForEach(vm.completedQuests) { quest in
          HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
              Text(quest.title)
                .font(.system(size: 13, weight: .medium))

              HStack(spacing: 3) {
                Image(systemName: "calendar")
                  .font(.system(size: 8))
                Text("\(formatDate(quest.completedAt)) \u{00B7} +\(quest.xpEarned ?? 0) XP \u{00B7} $\(String(format: "%.2f", quest.rewardAmount ?? 0))")
                  .font(.system(size: 11))
              }
              .foregroundColor(.gray)
            }

            Spacer()

            Text(quest.grade ?? "-")
              .font(.system(size: 17, weight: .semibold))
              .monospacedDigit()

            Image(systemName: "chevron.right")
              .font(.system(size: 12))
              .foregroundColor(.gray)
          }
          .padding(.vertical, 14)
          .padding(.horizontal, 20)
          .overlay(
            Rectangle()
              .fill(Color(.systemGray5))
              .frame(height: 0.5),
            alignment: .bottom
          )
        }
      }
    }
  }

  // MARK: - Badges

  private var badgesContent: some View {
    VStack(alignment: .leading, spacing: 12) {
      Text("\(vm.unlockedBadgeCount) of \(vm.badges.count) unlocked")
        .font(.system(size: 11))
        .foregroundColor(.gray)

      let columns = Array(repeating: GridItem(.flexible(), spacing: 16), count: 4)
      LazyVGrid(columns: columns, spacing: 16) {
        ForEach(vm.badges) { badge in
          VStack(spacing: 5) {
            ZStack {
              RoundedRectangle(cornerRadius: 14)
                .fill(Color(.systemGray6))
                .frame(width: 54, height: 54)
                .overlay(
                  RoundedRectangle(cornerRadius: 14)
                    .stroke(Color(.systemGray5), lineWidth: 0.5)
                )

              Text(badge.emoji)
                .font(.system(size: 20))
            }

            Text(badge.name)
              .font(.system(size: 9, weight: .medium))
              .foregroundColor(.gray)
              .multilineTextAlignment(.center)
              .lineLimit(2)
              .frame(maxWidth: 60)
          }
          .opacity(badge.unlocked ? 1 : 0.25)
        }
      }
    }
    .padding(.horizontal, 20)
    .padding(.top, 6)
  }

  // MARK: - Personality

  private var personalityContent: some View {
    VStack(spacing: 16) {
      if vm.personalityTraits.isEmpty {
        Text("Complete quests to build your personality profile")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .padding(.top, 40)
      } else {
        VStack(spacing: 14) {
          ForEach(vm.personalityTraits, id: \.label) { trait in
            VStack(spacing: 4) {
              HStack {
                Text(trait.label)
                  .font(.system(size: 11))
                  .foregroundColor(.gray)
                Spacer()
                Text("\(trait.value)%")
                  .font(.system(size: 11, weight: .medium))
              }

              GeometryReader { geometry in
                ZStack(alignment: .leading) {
                  RoundedRectangle(cornerRadius: 2)
                    .fill(Color(.systemGray6))
                    .frame(height: 3)

                  RoundedRectangle(cornerRadius: 2)
                    .fill(Color.black)
                    .frame(width: geometry.size.width * Double(trait.value) / 100, height: 3)
                }
              }
              .frame(height: 3)
            }
          }
        }
      }
    }
    .padding(.horizontal, 20)
    .padding(.top, 6)
  }

  private func formatDate(_ date: Date?) -> String {
    guard let date = date else { return "-" }
    let f = DateFormatter()
    f.dateFormat = "MMM d, yyyy"
    return f.string(from: date)
  }
}
