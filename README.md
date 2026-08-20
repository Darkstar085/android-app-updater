# Android App Updater

Automatically tracks GitHub releases, downloads updated apps, creates one consolidated GitHub Release, and publishes new app updates to Telegram. 🚀

## ✨ How It Works

Every run uses the same pipeline for every configured app:

1. 🔎 Discover the latest GitHub release.
2. 🎯 Select one matching APK/EXE asset using the app configuration.
3. 📥 Download it into an isolated per-app folder.
4. 🔐 Extract the version from the APK metadata or executable filename.
5. 🧮 Compare it with the stored version.
6. 🏷️ Rename only changed files to `AppName_VERSION.apk` / `.exe`.
7. 📝 Generate captions and release notes.
8. 📦 Create one GitHub Release containing all updated apps.
9. 📲 Deliver the release to Telegram.
10. 💾 Commit the new version state.

A missing or broken asset for one repository is reported and skipped; it does not overwrite or delete another app's download.

## 🧩 App Configuration

All app-specific settings live in [`apps.json`](./.github/scripts/apps.json). Each entry contains:

- GitHub repository
- preferred asset pattern(s)
- optional exclusions
- display description and emoji
- changelog URL

This means adding or changing an app no longer requires editing a large shell script.

## 📱 Apps Covered

- 📥 **ABDownloadManager** — Powerful download manager with multi-threading
- 💻 **Acode** — Lightweight yet powerful code editor
- 🔐 **Aegis** — Modern two-factor authentication app
- 📺 **NopeRemote** — Open-source universal IR remote control app for Android
- 🧹 **Kudu** — Open-source system cleaner and security scanner for Windows, macOS and Linux
- 🎵 **SpotiFLAC** — Open-source music player and lossless audio downloader for Android
- 🎬 **LibreCuts** — Free, open-source video editor for Android
- 🗺️ **OrganicMaps** — Privacy-focused offline maps and navigation app
- 🙈 **AmarokHider** — Hide apps as your choice
- 🎭 **Arcticons** — Modern icon pack and theming app
- 🔑 **Bitwarden** — Open-source password manager with cloud sync
- 🌦️ **BreezyWeather** — Clean, customizable open-source weather app
- 🍒 **Cherrygram** — Enhanced Telegram client with extra features
- 🔄 **ConverterNOW** — Simple unit and currency converter
- 🌐 **Cromite** — Bromite-based privacy browser
- 💻 **CpuInfo** — Detailed CPU info tool
- 🎨 **DeltaIcons** — Beautiful, minimal icon pack
- 📷 **DotGallery** — Jetpack Compose-based photo gallery app
- 🦆 **DuckDuckGo** — Private, tracker-blocking browser
- ⌨️ **Florisboard** — Privacy-friendly Android keyboard
- 🤳 **Flip2DND** — Flip your phone to toggle Do Not Disturb automatically
- 🧮 **Fossify_Calculator** — Open-source, privacy-friendly calculator by Fossify
- ⌨️ **Fossify_Keyboard** — Easy keyboard for inserting texts, special characters and numbers
- 🎶 **Fossify_MusicPlayer** — Modern music player by Fossify
- 🗒️ **Fossify_Notes** — Secure, privacy-focused notes app by Fossify
- 🎤 **Fossify_VoiceRecorder** — Simple, privacy-respecting voice recorder by Fossify
- 🎼 **Gramophone** — Minimalist, elegant music player
- 🦦 **IceravenBrowser** — Privacy-focused web browser
- 🖼️ **ImageToolbox** — All-in-one image editing and viewing app
- 🔒 **LibreTube** — Open-source YouTube app focusing on privacy
- 📤 **LocalSend** — Secure, local file sharing app
- 🧹 **LTECleanerFOSS** — Clean up unnecessary files to free up space
- 🪄 **Magisk** — Powerful systemless rooting solution
- 🧩 **MicroG_RE** — MicroG RE - Enhanced Play Services compatibility
- 📖 **MoeList** — Anime and manga tracking app
- 📱 **Momogram** — Telegram client with privacy and customization features
- 🐱 **Nekogram** — Feature-rich Telegram client with enhanced privacy
- 🛠️ **Omni** — All-in-one tool app with Compass, Spirit Level, Ruler and Flashlight
- 🎧 **OuterTune** — A Material 3 YouTube Music client & local music player for Android
- 🎵 **Pixelplay** — Lightweight music player with Material You design
- 🎧 **PhonographPlus** — Enhanced music player fork
- 🗂️ **PrismFileExplorer** — Powerful, material design file explorer
- 📥 **Quantum_Download_Manager** — A modern, open-source download manager for Windows
- 🤖 **Shizuku** — Use system APIs directly with adb/root privileges from normal apps
- 📦 **RetroMusicPlayer** — No description available
- 🎬 **Morphe_YouTube** — YouTube with ad-block, background play, sponsor block and more
- 🎵 **Morphe_YTMusic** — YouTube Music with premium unlock, ad-block and advanced playback
- 📷 **Morphe_GooglePhotos** — Google Photos with premium/unlocked features
- 🧩 **Morphe_MicroG** — MicroG for Morphe - enables Google sign-in
- 🛠️ **Morphe_Manager** — Manage and install Morphe patches easily
- 🧹 **Sdmaid** — Powerful system cleaning tool
- 🎵 **SimpMusic** — Lightweight YT music player with Material You support
- 🎼 **Symphony** — Lightweight music player for Android 9+
- 🖥️ **Termux** — Terminal emulator and Linux environment for Android
- 📧 **ThunderbirdAndroid** — Official Thunderbird email client for Android
- 💻 **VisualCodeSpace** — Lightweight, feature-rich Android code editor and IDE
- ☁️ **WeatherMaster** — Modern weather app with graphs
- ✏️ **XedEditor** — Simple and fast text/code editor
- ⬇️ **Ytdlnis** — YouTube downloader with advanced features

## 📦 Releases

Each update creates **one** GitHub Release containing only the apps whose versions changed.

Example filenames:

```text
ConverterNOW_v4.6.3.apk
Kudu_v2.1.0.exe
```

Release notes show the complete update list and any repositories whose assets could not be downloaded.

## 📲 Telegram

New release files are delivered automatically to the Telegram channel:

- 📢 [Darkstar's Hub](https://t.me/darkstar085_channel)

Telegram captions do not repeat the uploaded filename because Telegram already displays it with the file.

## ⚙️ Reliability

- 🗂️ Every app downloads into its own temporary directory.
- 🎯 Only one selected release asset is processed per app.
- 🚫 No global `rm *.apk` cleanup can delete another app's download.
- 🔎 Actual downloaded filenames are detected instead of assuming `app-release.apk`.
- 🧾 Failed, skipped, and updated apps are summarized in the workflow.
- 🔁 Version tracking prevents duplicate releases.
- 📤 Telegram uploads use retry and FloodWait handling.
- ⏭️ Recent Telegram filenames are checked to avoid duplicate posts.

## 🔐 Required GitHub Secrets

```text
TOKEN
TELEGRAM_API_ID
TELEGRAM_API_HASH
TELEGRAM_SESSION
TELEGRAM_CHAT_ID
```

Keep these values private and store them only in GitHub repository secrets.

## 🤝 Requests & Support

- 💬 Telegram group: [Darkstar's Group](https://t.me/darkstar085_group)
- 🐛 Open a GitHub issue for workflow or app configuration problems.

## 📜 License

The workflow and automation code are licensed under the [MIT License](./LICENSE).
Third-party APK/EXE files remain the property of their respective copyright holders.
