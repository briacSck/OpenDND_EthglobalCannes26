/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct LeaderboardEntry: Identifiable {
  let id = UUID()
  let rank: Int
  let name: String
  let avatar: String
  let xp: Int
  let level: Int
  let isYou: Bool
}

struct FriendActivity: Identifiable {
  let id = UUID()
  let name: String
  let avatar: String
  let action: String
  let grade: String?
  let time: String
}

struct SocialView: View {
  @State private var selectedTab: SocialTab = .leaderboard

  enum SocialTab: String, CaseIterable {
    case leaderboard
    case activity
  }

  private let leaderboard: [LeaderboardEntry] = [
    LeaderboardEntry(rank: 1, name: "Alex K.", avatar: "A", xp: 4820, level: 18, isYou: false),
    LeaderboardEntry(rank: 2, name: "Sarah M.", avatar: "S", xp: 4510, level: 17, isYou: false),
    LeaderboardEntry(rank: 3, name: "You", avatar: "Y", xp: 4280, level: 16, isYou: true),
    LeaderboardEntry(rank: 4, name: "Mike R.", avatar: "M", xp: 3900, level: 15, isYou: false),
    LeaderboardEntry(rank: 5, name: "Luna Z.", avatar: "L", xp: 3750, level: 14, isYou: false),
    LeaderboardEntry(rank: 6, name: "Dev P.", avatar: "D", xp: 3200, level: 13, isYou: false),
    LeaderboardEntry(rank: 7, name: "Nora T.", avatar: "N", xp: 2980, level: 12, isYou: false),
  ]

  private let friendActivity: [FriendActivity] = [
    FriendActivity(name: "Alex K.", avatar: "A", action: "completed Operation Blackout", grade: "S", time: "2h ago"),
    FriendActivity(name: "Sarah M.", avatar: "S", action: "unlocked Sharpshooter badge", grade: nil, time: "4h ago"),
    FriendActivity(name: "Luna Z.", avatar: "L", action: "started The Heist", grade: nil, time: "5h ago"),
    FriendActivity(name: "Mike R.", avatar: "M", action: "completed Dead Drop", grade: "A-", time: "8h ago"),
    FriendActivity(name: "Dev P.", avatar: "D", action: "reached Level 13", grade: nil, time: "1d ago"),
  ]

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        // Header
        VStack(alignment: .leading, spacing: 2) {
          Text("Friends")
            .font(.system(size: 20, weight: .semibold))
          Text("See what your squad is up to")
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
        if selectedTab == .leaderboard {
          leaderboardContent
        } else {
          activityContent
        }
      }
    }
    .background(Color.white)
  }

  // MARK: - Tab Selector

  private var tabSelector: some View {
    HStack(spacing: 3) {
      ForEach(SocialTab.allCases, id: \.self) { tab in
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

  // MARK: - Leaderboard

  private var leaderboardContent: some View {
    VStack(spacing: 0) {
      ForEach(leaderboard) { user in
        HStack(spacing: 10) {
          Text("\(user.rank)")
            .font(.system(size: 11, weight: .medium))
            .foregroundColor(.gray)
            .frame(width: 16, alignment: .trailing)
            .monospacedDigit()

          Text(user.avatar)
            .font(.system(size: 11, weight: .semibold))
            .frame(width: 30, height: 30)
            .background(Color(.systemGray6))
            .clipShape(Circle())
            .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

          VStack(alignment: .leading, spacing: 1) {
            HStack(spacing: 4) {
              Text(user.name)
                .font(.system(size: 13, weight: .medium))
              if user.isYou {
                Text("you")
                  .font(.system(size: 9))
                  .foregroundColor(.gray)
              }
            }
            Text("Level \(user.level)")
              .font(.system(size: 11))
              .foregroundColor(.gray)
          }

          Spacer()

          Text("\(user.xp.formatted())")
            .font(.system(size: 13, weight: .medium))
            .monospacedDigit()
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 20)
        .background(user.isYou ? Color(.systemGray6) : Color.clear)
        .overlay(
          Rectangle()
            .fill(Color(.systemGray5))
            .frame(height: 0.5),
          alignment: .bottom
        )
      }
    }
  }

  // MARK: - Activity Feed

  private var activityContent: some View {
    VStack(spacing: 0) {
      ForEach(friendActivity) { activity in
        HStack(spacing: 10) {
          Text(activity.avatar)
            .font(.system(size: 11, weight: .semibold))
            .frame(width: 30, height: 30)
            .background(Color(.systemGray6))
            .clipShape(Circle())
            .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

          VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 0) {
              Text(activity.name)
                .font(.system(size: 13, weight: .medium))
              Text(" \(activity.action)")
                .font(.system(size: 13))
                .foregroundColor(.gray)
            }

            HStack(spacing: 3) {
              Image(systemName: "clock")
                .font(.system(size: 8))
              Text(activity.time)
                .font(.system(size: 11))
            }
            .foregroundColor(.gray)
          }

          Spacer()

          if let grade = activity.grade {
            Text(grade)
              .font(.system(size: 13, weight: .semibold))
          }

          Image(systemName: "chevron.right")
            .font(.system(size: 12))
            .foregroundColor(.gray)
        }
        .padding(.vertical, 12)
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
