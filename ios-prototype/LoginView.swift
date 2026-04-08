import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("学习笔记")
                        .font(.largeTitle.weight(.bold))
                    Text("欢迎回来，登录后查看你的学习主题")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                InfoCard(title: "服务器") {
                    TextField("http://127.0.0.1:8000", text: $session.serverBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(Color(.systemBackground))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color(.systemGray4), lineWidth: 1)
                        )
                    Text("模拟器建议: http://127.0.0.1:8000")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Text("真机建议: http://你的Mac局域网IP:8000")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                InfoCard(title: "登录") {
                    TextField("用户名", text: $session.username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(Color(.systemBackground))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color(.systemGray4), lineWidth: 1)
                        )

                    SecureField("密码", text: $session.password)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(Color(.systemBackground))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .stroke(Color(.systemGray4), lineWidth: 1)
                        )
                }

                Button {
                    Task {
                        await session.login()
                    }
                } label: {
                    if session.isLoading {
                        HStack {
                            Spacer()
                            ProgressView()
                                .tint(.white)
                            Spacer()
                        }
                        .padding(.vertical, 13)
                    } else {
                        Text("立即登录")
                            .fontWeight(.semibold)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 13)
                    }
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(session.username.isEmpty || session.password.isEmpty || session.isLoading ? Color.gray : Color.blue)
                )
                .disabled(session.username.isEmpty || session.password.isEmpty || session.isLoading)

                if !session.errorMessage.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("错误")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(session.errorMessage)
                            .foregroundStyle(.red)
                            .font(.subheadline)
                    }
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Color(.secondarySystemGroupedBackground))
                    )
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 16)
            .padding(.bottom, 28)
        }
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct InfoCard<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            content
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
    }
}
