/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct SocialView: View {
  @StateObject private var vm = SocialViewModel()
  @State private var selectedTab: SocialTab = .leaderboard

  enum SocialTab: String, CaseIterable {
    case leaderboard
    case activity
  }

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

        if vm.isLoading {
          ProgressView()
            .padding(.top, 40)
        } else if selectedTab == .leaderboard {
          leaderboardContent
        } else {
          activityContent
        }
      }
    }
    .background(Color.white)
    .onAppear { vm.load() }
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
      if vm.leaderboard.isEmpty {
        Text("No players yet")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .padding(.top, 40)
      } else {
        ForEach(vm.leaderboard) { user in
          let isYou = user.id == vm.currentUserId
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
                Text(isYou ? "You" : user.name)
                  .font(.system(size: 13, weight: .medium))
                if isYou {
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
          .background(isYou ? Color(.systemGray6) : Color.clear)
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

  // MARK: - Activity Feed

  private var activityContent: some View {
    VStack(spacing: 0) {
      if vm.activity.isEmpty {
        Text("No recent activity")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .padding(.top, 40)
      } else {
        ForEach(vm.activity) { activity in
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
                Text(formatRelativeTime(activity.time))
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

  private func formatRelativeTime(_ date: Date?) -> String {
    guard let date = date else { return "-" }
    let interval = Date().timeIntervalSince(date)
    if interval < 3600 { return "\(Int(interval / 60))m ago" }
    if interval < 86400 { return "\(Int(interval / 3600))h ago" }
    return "\(Int(interval / 86400))d ago"
  }
}
