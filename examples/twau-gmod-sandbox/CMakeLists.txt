cmake_minimum_required(VERSION 3.20)
project(twau_gmod_sandbox CXX C)

# The Wolf Among Us is a 32-bit game: configure with  cmake -A Win32
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
  message(FATAL_ERROR "Build for Win32: cmake -S . -B build -A Win32")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
add_compile_definitions(WIN32_LEAN_AND_MEAN NOMINMAX _CRT_SECURE_NO_WARNINGS)

# -DTWAU_ASSETSCAN_ONLY=ON builds just the offline checker (needs only zlib).
option(TWAU_ASSETSCAN_ONLY "Build only twau_assetscan" OFF)

include(FetchContent)
FetchContent_Declare(zlib    GIT_REPOSITORY https://github.com/madler/zlib.git     GIT_TAG v1.3.1)
set(ZLIB_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(zlib)

# Archive/model readers: shared by the game plugin and the offline checker.
add_library(assetbridge STATIC src/AssetBridge.cpp)
target_include_directories(assetbridge PUBLIC src ${zlib_SOURCE_DIR} ${zlib_BINARY_DIR})
target_link_libraries(assetbridge PUBLIC zlibstatic)

# Offline checker: runs AssetBridge against the real installs, no game launch.
add_executable(twau_assetscan tools/assetscan.cpp)
target_link_libraries(twau_assetscan PRIVATE assetbridge)

if(TWAU_ASSETSCAN_ONLY)
  return()
endif()

FetchContent_Declare(imgui   GIT_REPOSITORY https://github.com/ocornut/imgui.git   GIT_TAG v1.91.9b)
FetchContent_Declare(minhook GIT_REPOSITORY https://github.com/TsudaKageyu/minhook.git GIT_TAG v1.3.3)
FetchContent_MakeAvailable(imgui minhook)

# MinHook 1.3.3 ships no CMakeLists: build its sources directly.
add_library(minhook_static STATIC
  ${minhook_SOURCE_DIR}/src/hook.c ${minhook_SOURCE_DIR}/src/buffer.c ${minhook_SOURCE_DIR}/src/trampoline.c
  ${minhook_SOURCE_DIR}/src/hde/hde32.c ${minhook_SOURCE_DIR}/src/hde/hde64.c)
target_include_directories(minhook_static PUBLIC ${minhook_SOURCE_DIR}/include)

add_library(imgui_dx9 STATIC
  ${imgui_SOURCE_DIR}/imgui.cpp ${imgui_SOURCE_DIR}/imgui_draw.cpp ${imgui_SOURCE_DIR}/imgui_tables.cpp
  ${imgui_SOURCE_DIR}/imgui_widgets.cpp
  ${imgui_SOURCE_DIR}/backends/imgui_impl_dx9.cpp ${imgui_SOURCE_DIR}/backends/imgui_impl_win32.cpp)
target_include_directories(imgui_dx9 PUBLIC ${imgui_SOURCE_DIR} ${imgui_SOURCE_DIR}/backends)

# The plugin: TWAU_GMod.asi
add_library(TWAU_GMod SHARED
  src/dllmain.cpp src/LuaBridge.cpp src/StateAndCameraManager.cpp src/GModMenuAndHUD.cpp
  src/CombatAndRagdollPhysics.cpp src/Audio.cpp)
set_target_properties(TWAU_GMod PROPERTIES SUFFIX ".asi")
target_link_libraries(TWAU_GMod PRIVATE assetbridge imgui_dx9 minhook_static d3d9 dxguid xaudio2 windowscodecs ole32)

# The loader: dinput8.dll (forwards to the system dinput8, then loads *.asi from the game folder)
add_library(dinput8 SHARED src/dinput8_proxy.cpp src/dinput8.def)
set_target_properties(dinput8 PROPERTIES OUTPUT_NAME "dinput8")
