/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 * All rights reserved.
 *
 * This source code is licensed under the license found in the
 * LICENSE file in the root directory of this source tree.
 */

import MWDATCore
import SwiftUI

struct TabBarView: View {
  let wearables: WearablesInterface
  @ObservedObject var wearablesVM: WearablesViewModel
  @State private var selectedTab = 0

  var body: some View {
    TabView(selection: $selectedTab) {
      // Quest tab
      NavigationView {
        QuestView()
      }
      .tabItem {
        Image(systemName: "shield.lefthalf.filled")
        Text("Quest")
      }
      .tag(0)

      // History tab
      NavigationView {
        HistoryView()
      }
      .tabItem {
        Image(systemName: "clock.arrow.circlepath")
        Text("History")
      }
      .tag(1)

      // Camera tab (existing functionality)
      StreamSessionView(wearables: wearables, wearablesVM: wearablesVM)
        .tabItem {
          Image(systemName: "camera")
          Text("Camera")
        }
        .tag(2)

      // Wallet tab
      NavigationView {
        WalletView()
      }
      .tabItem {
        Image(systemName: "wallet.pass")
        Text("Wallet")
      }
      .tag(3)

      // Social tab
      NavigationView {
        SocialView()
      }
      .tabItem {
        Image(systemName: "person.2")
        Text("Friends")
      }
      .tag(4)
    }
    .tint(.black)
  }
}
