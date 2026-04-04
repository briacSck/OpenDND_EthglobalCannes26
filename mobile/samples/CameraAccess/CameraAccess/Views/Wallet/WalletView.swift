/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import SwiftUI

struct Transaction: Identifiable {
  let id: Int
  let type: String // "credit" or "debit"
  let label: String
  let amount: String
  let date: String
}

struct WalletView: View {
  private let transactions: [Transaction] = [
    Transaction(id: 1, type: "credit", label: "Operation Nightfall", amount: "+$24.50", date: "Mar 28"),
    Transaction(id: 2, type: "debit", label: "Quest unlock: Sunrise", amount: "-$5.00", date: "Mar 28"),
    Transaction(id: 3, type: "credit", label: "The Moscow Exchange", amount: "+$18.00", date: "Mar 22"),
    Transaction(id: 4, type: "debit", label: "Premium gear pack", amount: "-$8.00", date: "Mar 20"),
    Transaction(id: 5, type: "credit", label: "Dead Drop", amount: "+$12.50", date: "Mar 15"),
    Transaction(id: 6, type: "credit", label: "Weekly bonus", amount: "+$5.00", date: "Mar 14"),
  ]

  var body: some View {
    ScrollView {
      VStack(spacing: 0) {
        // Header - Balance
        VStack(alignment: .leading, spacing: 4) {
          Text("Available Balance")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
            .tracking(1)

          Text("$67.00")
            .font(.system(size: 34, weight: .semibold))
            .tracking(-0.5)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.top, 16)
        .padding(.bottom, 20)
        .overlay(
          Rectangle()
            .fill(Color(.systemGray5))
            .frame(height: 0.5),
          alignment: .bottom
        )

        // Sub-balances
        HStack(spacing: 0) {
          // Locked
          VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
              Image(systemName: "lock")
                .font(.system(size: 10))
              Text("Locked")
                .font(.system(size: 9, weight: .medium))
                .textCase(.uppercase)
            }
            .foregroundColor(.gray)

            Text("$35.00")
              .font(.system(size: 17, weight: .semibold))

            Text("Reserved for quests")
              .font(.system(size: 9))
              .foregroundColor(.gray)
          }
          .frame(maxWidth: .infinity, alignment: .leading)
          .padding(.horizontal, 20)
          .padding(.vertical, 14)

          Rectangle()
            .fill(Color(.systemGray5))
            .frame(width: 0.5)

          // Pending
          VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
              Image(systemName: "clock")
                .font(.system(size: 10))
              Text("Pending")
                .font(.system(size: 9, weight: .medium))
                .textCase(.uppercase)
            }
            .foregroundColor(.gray)

            Text("$24.50")
              .font(.system(size: 17, weight: .semibold))

            Text("Arriving in ~2h")
              .font(.system(size: 9))
              .foregroundColor(.gray)
          }
          .frame(maxWidth: .infinity, alignment: .leading)
          .padding(.horizontal, 20)
          .padding(.vertical, 14)
        }
        .overlay(
          Rectangle()
            .fill(Color(.systemGray5))
            .frame(height: 0.5),
          alignment: .bottom
        )

        // Actions
        HStack(spacing: 10) {
          actionButton(icon: "arrow.down.left", label: "Deposit")
          actionButton(icon: "arrow.up.right", label: "Withdraw")
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)

        // Transactions
        VStack(alignment: .leading, spacing: 8) {
          Text("Transactions")
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(.gray)
            .textCase(.uppercase)
            .tracking(1)

          VStack(spacing: 0) {
            ForEach(transactions) { tx in
              HStack(spacing: 10) {
                ZStack {
                  Circle()
                    .fill(Color(.systemGray6))
                    .frame(width: 28, height: 28)

                  Image(systemName: tx.type == "credit" ? "arrow.down.left" : "arrow.up.right")
                    .font(.system(size: 12))
                    .foregroundColor(tx.type == "credit" ? .black : .gray)
                }

                VStack(alignment: .leading, spacing: 1) {
                  Text(tx.label)
                    .font(.system(size: 13))
                  Text(tx.date)
                    .font(.system(size: 11))
                    .foregroundColor(.gray)
                }

                Spacer()

                Text(tx.amount)
                  .font(.system(size: 13, weight: .medium))
                  .foregroundColor(tx.type == "credit" ? .black : .gray)
                  .monospacedDigit()
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
        }
        .padding(.horizontal, 20)
      }
    }
    .background(Color.white)
  }

  private func actionButton(icon: String, label: String) -> some View {
    Button {
    } label: {
      HStack(spacing: 6) {
        Image(systemName: icon)
          .font(.system(size: 14))
        Text(label)
          .font(.system(size: 13, weight: .medium))
      }
      .foregroundColor(.black)
      .frame(maxWidth: .infinity)
      .padding(.vertical, 10)
      .overlay(
        RoundedRectangle(cornerRadius: 8)
          .stroke(Color(.systemGray4), lineWidth: 0.5)
      )
    }
  }
}
