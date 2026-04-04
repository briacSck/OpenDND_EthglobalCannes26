/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct PostQuestView: View {
  @Environment(\.dismiss) private var dismiss
  @State private var currentSlide = 0

  private let totalSlides = 5

  var body: some View {
    ZStack {
      Color.white.edgesIgnoringSafeArea(.all)

      // Slides
      TabView(selection: $currentSlide) {
        completionSlide.tag(0)
        gradeSlide.tag(1)
        clipSlide.tag(2)
        rewardSlide.tag(3)
        nextQuestSlide.tag(4)
      }
      .tabViewStyle(.page(indexDisplayMode: .never))

      // Top bar
      VStack {
        HStack {
          Button {
            dismiss()
          } label: {
            Image(systemName: "arrow.left")
              .font(.system(size: 14))
              .foregroundColor(.black)
              .frame(width: 34, height: 34)
              .background(Color(.systemGray6))
              .clipShape(Circle())
              .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))
          }

          Spacer()

          // Progress dots
          HStack(spacing: 4) {
            ForEach(0..<totalSlides, id: \.self) { i in
              RoundedRectangle(cornerRadius: 1)
                .fill(i == currentSlide ? Color.black : (i < currentSlide ? Color.black.opacity(0.3) : Color(.systemGray4)))
                .frame(width: i == currentSlide ? 18 : 5, height: 2)
                .animation(.easeInOut(duration: 0.3), value: currentSlide)
            }
          }

          Spacer()

          // Invisible spacer to balance the back button
          Color.clear
            .frame(width: 34, height: 34)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)

        Spacer()
      }
    }
    .navigationBarHidden(true)
  }

  // MARK: - Slide 1: Completion

  private var completionSlide: some View {
    VStack(spacing: 0) {
      Spacer()

      ZStack {
        Circle()
          .fill(Color(.systemGray6))
          .frame(width: 60, height: 60)
          .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

        Image(systemName: "trophy")
          .font(.system(size: 24))
      }
      .padding(.bottom, 20)

      Text("Quest Complete")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(2)
        .padding(.bottom, 6)

      Text("Operation Nightfall")
        .font(.system(size: 22, weight: .semibold))
        .padding(.bottom, 2)

      Text("Mission accomplished")
        .font(.system(size: 13))
        .foregroundColor(.gray)
        .padding(.bottom, 28)

      HStack(spacing: 0) {
        statItem(value: "47m", label: "Time")

        Rectangle()
          .fill(Color(.systemGray5))
          .frame(width: 0.5, height: 32)

        statItem(value: "5/5", label: "Steps")

        Rectangle()
          .fill(Color(.systemGray5))
          .frame(width: 0.5, height: 32)

        statItem(value: "0", label: "Fails")
      }

      Spacer()
    }
  }

  // MARK: - Slide 2: Grade

  private var gradeSlide: some View {
    VStack(spacing: 0) {
      Spacer()

      Text("Performance Review")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(2)
        .padding(.bottom, 20)

      Text("A+")
        .font(.system(size: 64, weight: .bold))
        .padding(.bottom, 4)

      Text("Top 3% of all players")
        .font(.system(size: 13))
        .foregroundColor(.gray)
        .padding(.bottom, 32)

      VStack(spacing: 6) {
        achievementRow(title: "Stealth Master", desc: "Zero alerts triggered")
        achievementRow(title: "Smooth Talker", desc: "Perfect interrogation")
        achievementRow(title: "Speed Demon", desc: "12 min under par")
      }
      .padding(.horizontal, 32)

      Spacer()
    }
    .background(Color(.systemGray6).opacity(0.5))
  }

  // MARK: - Slide 3: Best Clip

  private var clipSlide: some View {
    VStack(spacing: 0) {
      Spacer()

      Text("Best Moment")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(2)
        .padding(.bottom, 20)

      ZStack {
        RoundedRectangle(cornerRadius: 16)
          .fill(Color(.systemGray6))
          .frame(width: 220, height: 340)
          .overlay(
            RoundedRectangle(cornerRadius: 16)
              .stroke(Color(.systemGray5), lineWidth: 0.5)
          )

        // Play button
        ZStack {
          Circle()
            .fill(Color.white)
            .frame(width: 44, height: 44)
            .overlay(Circle().stroke(Color(.systemGray5), lineWidth: 0.5))

          Image(systemName: "play.fill")
            .font(.system(size: 16))
            .foregroundColor(.black)
            .offset(x: 1)
        }

        // Bottom label
        VStack {
          Spacer()
          VStack(alignment: .leading, spacing: 1) {
            Text("The Vault Escape")
              .font(.system(size: 13, weight: .medium))
            Text("0:47")
              .font(.system(size: 11))
              .foregroundColor(.gray)
          }
          .frame(maxWidth: .infinity, alignment: .leading)
          .padding(12)
          .background(
            LinearGradient(
              colors: [.white, .white.opacity(0)],
              startPoint: .bottom,
              endPoint: .top
            )
          )
        }
        .frame(width: 220, height: 340)
        .clipShape(RoundedRectangle(cornerRadius: 16))
      }
      .padding(.bottom, 20)

      HStack(spacing: 8) {
        Button {
        } label: {
          HStack(spacing: 5) {
            Image(systemName: "square.and.arrow.up")
              .font(.system(size: 12))
            Text("Share")
              .font(.system(size: 13, weight: .medium))
          }
          .foregroundColor(.white)
          .padding(.horizontal, 16)
          .padding(.vertical, 9)
          .background(Color.black)
          .clipShape(Capsule())
        }

        Button {
        } label: {
          Text("Save")
            .font(.system(size: 13, weight: .medium))
            .foregroundColor(.gray)
            .padding(.horizontal, 16)
            .padding(.vertical, 9)
            .overlay(Capsule().stroke(Color(.systemGray4), lineWidth: 0.5))
        }
      }

      Spacer()
    }
  }

  // MARK: - Slide 4: Reward

  private var rewardSlide: some View {
    VStack(spacing: 0) {
      Spacer()

      Text("Rewards")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(2)
        .padding(.bottom, 20)

      Text("$24.50")
        .font(.system(size: 40, weight: .semibold))
        .padding(.bottom, 2)

      Text("Quest reward")
        .font(.system(size: 13))
        .foregroundColor(.gray)
        .padding(.bottom, 28)

      HStack(spacing: 0) {
        VStack(spacing: 2) {
          Text("+340")
            .font(.system(size: 18, weight: .semibold))
          Text("XP")
            .font(.system(size: 9, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
        }
        .frame(width: 80)

        Rectangle()
          .fill(Color(.systemGray5))
          .frame(width: 0.5, height: 32)

        VStack(spacing: 2) {
          Text("+2")
            .font(.system(size: 18, weight: .semibold))
          Text("Badges")
            .font(.system(size: 9, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
        }
        .frame(width: 80)
      }
      .padding(.bottom, 28)

      HStack(spacing: 4) {
        Image(systemName: "clock")
          .font(.system(size: 10))
        Text("Payment arrives in ~2 hours")
          .font(.system(size: 11))
      }
      .foregroundColor(.gray)

      Spacer()
    }
    .background(Color(.systemGray6).opacity(0.5))
  }

  // MARK: - Slide 5: Next Quest

  private var nextQuestSlide: some View {
    VStack(spacing: 0) {
      Spacer()

      Text("Up Next")
        .font(.system(size: 10, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
        .tracking(2)
        .padding(.bottom, 20)

      VStack(spacing: 16) {
        Text("Operation Sunrise")
          .font(.system(size: 17, weight: .semibold))

        Text("A new threat emerges from the ashes. Your skills have not gone unnoticed.")
          .font(.system(size: 13))
          .foregroundColor(.gray)
          .multilineTextAlignment(.center)

        HStack(spacing: 20) {
          VStack(spacing: 2) {
            Text("500 XP")
              .font(.system(size: 13, weight: .semibold))
            Text("Reward")
              .font(.system(size: 9))
              .foregroundColor(.gray)
          }
          VStack(spacing: 2) {
            Text("Hard")
              .font(.system(size: 13, weight: .semibold))
            Text("Difficulty")
              .font(.system(size: 9))
              .foregroundColor(.gray)
          }
          VStack(spacing: 2) {
            Text("$35")
              .font(.system(size: 13, weight: .semibold))
            Text("Payout")
              .font(.system(size: 9))
              .foregroundColor(.gray)
          }
        }
      }
      .padding(24)
      .background(Color(.systemGray6))
      .cornerRadius(16)
      .overlay(
        RoundedRectangle(cornerRadius: 16)
          .stroke(Color(.systemGray5), lineWidth: 0.5)
      )
      .padding(.horizontal, 32)
      .padding(.bottom, 28)

      Button {
        dismiss()
      } label: {
        Text("Accept Quest")
          .font(.system(size: 14, weight: .medium))
          .foregroundColor(.white)
          .padding(.horizontal, 32)
          .padding(.vertical, 12)
          .background(Color.black)
          .clipShape(Capsule())
      }

      Spacer()
    }
  }

  // MARK: - Helpers

  private func statItem(value: String, label: String) -> some View {
    VStack(spacing: 2) {
      Text(value)
        .font(.system(size: 22, weight: .semibold))
      Text(label)
        .font(.system(size: 9, weight: .medium))
        .foregroundColor(.gray)
        .textCase(.uppercase)
    }
    .frame(maxWidth: .infinity)
  }

  private func achievementRow(title: String, desc: String) -> some View {
    HStack(spacing: 10) {
      Image(systemName: "star")
        .font(.system(size: 14))

      VStack(alignment: .leading, spacing: 1) {
        Text(title)
          .font(.system(size: 13, weight: .medium))
        Text(desc)
          .font(.system(size: 11))
          .foregroundColor(.gray)
      }

      Spacer()
    }
    .padding(10)
    .background(Color.white)
    .cornerRadius(12)
    .overlay(
      RoundedRectangle(cornerRadius: 12)
        .stroke(Color(.systemGray5), lineWidth: 0.5)
    )
  }
}
