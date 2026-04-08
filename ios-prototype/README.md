# iOS Prototype

This folder contains a minimal SwiftUI prototype for:

- login with JWT
- loading the topic list
- configurable server base URL for simulator and real-device testing

An Xcode project has already been generated:

- `LearningLogIOSPrototype.xcodeproj`

## Suggested next step on your Mac

1. Open `LearningLogIOSPrototype.xcodeproj` in Xcode.
2. Confirm deployment target is iOS 16.0 or lower than your target device OS (for iPhone 15 + iOS 17, this is compatible).
3. Choose an iPhone simulator or your real iPhone as destination.
4. Run the app.

## Important local networking note

If you run the Django server on the same Mac and want the iOS Simulator to access it, use:

- `http://127.0.0.1:8000`

If you later test on a real iPhone, replace that with your Mac's LAN IP.

The login page includes a `Server` section where you can edit and save this value.
