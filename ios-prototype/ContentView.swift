import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        NavigationStack {
            if session.isAuthenticated {
                TopicListView()
            } else {
                LoginView()
            }
        }
    }
}
