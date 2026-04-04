/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct CompletedQuest: Identifiable {
  let id: Int
  let title: String
  let date: String
  let grade: String
  let xp: Int
  let reward: String
}

struct BadgeItem: Identifiable {
  let id = UUID()
  let emoji: String
  let label: String
  let unlocked: Bool
}

struct PersonalityTrait: Identifiable {
  let id = UUID()
  let label: String
  let value: Int
}

struct HistoryView: View {
  @State private var selectedTab: HistoryTab = .quests

  enum HistoryTab: String, CaseIterable {
    case quests
    case badges
    case personality
  }

  private let completedQuests: [CompletedQuest] = [
    CompletedQuest(id: 1, title: "Operation Nightfall", date: "Mar 28, 2026", grade: "A+", xp: 340, reward: "$24.50"),
    CompletedQuest(id: 2, title: "The Moscow Exchange", date: "Mar 22, 2026", grade: "A", xp: 280, reward: "$18.00"),
    CompletedQuest(id: 3, title: "Dead Drop", date: "Mar 15, 2026", grade: "B+", xp: 210, reward: "$12.50"),
    CompletedQuest(id: 4, title: "Cold Trail", date: "Mar 8, 2026", grade: "A-", xp: 300, reward: "$20.00"),
    CompletedQuest(id: 5, title: "First Contact", date: "Mar 1, 2026", grade: "B", xp: 150, reward: "$8.00"),
  ]

  private let badges: [BadgeItem] = [
    BadgeItem(emoji: "🥷", label: "Shadow Agent", unlocked: true),
    BadgeItem(emoji: "🎯", label: "Perfect Shot", unlocked: true),
    BadgeItem(emoji: "🧠", label: "Mastermind", unlocked: true),
    BadgeItem(emoji: "⚡", label: "Speed Runner", unlocked: true),
    BadgeItem(emoji: "🛡️", label: "Untouchable", unlocked: true),
    BadgeItem(emoji: "💬", label: "Silver Tongue", unlocked: true),
    BadgeItem(emoji: "🔓", label: "Lockpicker", unlocked: false),
    BadgeItem(emoji: "🌐", label: "Globetrotter", unlocked: false),
  ]

  private let personalityTraits: [PersonalityTrait] = [
    PersonalityTrait(label: "Strategist", value: 85),
    PersonalityTrait(label: "Diplomat", value: 72),
    PersonalityTrait(label: "Fighter", value: 45),
    PersonalityTrait(label: "Hacker", value: 68),
    PersonalityTrait(label: "Leader", value: 90),
  ]

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        // Header
        VStack(alignment: .leading, spacing: 2) {
          Text("History")
            .font(.system(size: 20, weight: .semibold))
          Text("\(completedQuests.count) quests · Level 12")
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

        // Content
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
    .background(Color.white)
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
      ForEach(completedQuests) { quest in
        HStack(spacing: 10) {
          VStack(alignment: .leading, spacing: 2) {
            Text(quest.title)
              .font(.system(size: 13, weight: .medium))

            HStack(spacing: 3) {
              Image(systemName: "calendar")
                .font(.system(size: 8))
              Text("\(quest.date) · +\(quest.xp) XP · \(quest.reward)")
                .font(.system(size: 11))
            }
            .foregroundColor(.gray)
          }

          Spacer()

          Text(quest.grade)
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

  // MARK: - Badges

  private var badgesContent: some View {
    VStack(alignment: .leading, spacing: 12) {
      Text("\(badges.filter(\.unlocked).count) of \(badges.count) unlocked")
        .font(.system(size: 11))
        .foregroundColor(.gray)

      let columns = Array(repeating: GridItem(.flexible(), spacing: 16), count: 4)
      LazyVGrid(columns: columns, spacing: 16) {
        ForEach(badges) { badge in
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

            Text(badge.label)
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
      // Avatar section
      VStack(spacing: 4) {
        Text("🕵️")
          .font(.system(size: 28))
          .padding(.bottom, 4)

        Text("The Phantom Strategist")
          .font(.system(size: 15, weight: .semibold))

        Text("A calculated mind that prefers brains over brawn")
          .font(.system(size: 11))
          .foregroundColor(.gray)
      }
      .padding(.vertical, 20)

      // Trait bars
      VStack(spacing: 14) {
        ForEach(personalityTraits) { trait in
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
    .padding(.horizontal, 20)
    .padding(.top, 6)
  }
}
