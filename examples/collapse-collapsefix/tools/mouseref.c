/* C-56 probe: which DirectInput call takes and drops the shared system mouse reference.
   Reads dinput8 (SysWOW64 build 0xdbcea407) base+0x26100 (refcount) and +0x260F0 (flag array) after each step.
   Any argument adds a keeper device first, as collapsefix's mouse_keeper does.
   Local test tool only: the offsets are this PC's system DLL, other builds are refused.
   Build: zig cc -target x86-windows-gnu -O1 -o mouseref.exe mouseref.c -ldinput8 -ldxguid -luser32 */
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <stdio.h>

static unsigned char *g_di;
static void show(const char *step) {
    printf("%-34s refcount %ld  flags %p\n", step, *(volatile LONG *)(g_di + 0x26100), *(void *volatile *)(g_di + 0x260F0));
}
static LRESULT CALLBACK wp(HWND h, UINT m, WPARAM w, LPARAM l) { return DefWindowProcA(h, m, w, l); }

int main(int argc, char **argv) {
    IDirectInput8A *di;
    IDirectInputDevice8A *keep = 0, *a, *b;
    HRESULT hr;
    WNDCLASSA wc = {0};
    HWND wnd;
    int keeper = argc > 1;
    wc.lpfnWndProc = wp, wc.hInstance = GetModuleHandleA(0), wc.lpszClassName = "c56";
    RegisterClassA(&wc);
    wnd = CreateWindowA("c56", "c56", WS_OVERLAPPEDWINDOW | WS_VISIBLE, 0, 0, 300, 200, 0, 0, wc.hInstance, 0);
    SetForegroundWindow(wnd);
    hr = DirectInput8Create(GetModuleHandleA(0), DIRECTINPUT_VERSION, &IID_IDirectInput8A, (void **)&di, 0);
    g_di = (unsigned char *)GetModuleHandleA("dinput8.dll");
    {
        IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(g_di + ((IMAGE_DOS_HEADER *)g_di)->e_lfanew);
        printf("DirectInput8Create %08lx, dinput8 timestamp %08lx\n", hr, nt->FileHeader.TimeDateStamp);
        if (nt->FileHeader.TimeDateStamp != 0xdbcea407) return 1;
    }
    show("start");
    if (keeper) {
        hr = di->lpVtbl->CreateDevice(di, &GUID_SysMouse, &keep, 0);
        show("keeper CreateDevice");
    }
    hr = di->lpVtbl->CreateDevice(di, &GUID_SysMouse, &a, 0);
    show("A CreateDevice");
    hr = a->lpVtbl->SetDataFormat(a, &c_dfDIMouse2);
    show("A SetDataFormat");
    hr = a->lpVtbl->SetCooperativeLevel(a, wnd, DISCL_EXCLUSIVE | DISCL_FOREGROUND);
    printf("  coop %08lx\n", hr);
    show("A SetCooperativeLevel excl|fg");
    hr = a->lpVtbl->Acquire(a);
    printf("  acquire %08lx\n", hr);
    show("A Acquire");
    hr = di->lpVtbl->CreateDevice(di, &GUID_SysMouse, &b, 0);
    b->lpVtbl->SetDataFormat(b, &c_dfDIMouse2);
    show("B CreateDevice+SetDataFormat");
    a->lpVtbl->Unacquire(a);
    show("A Unacquire");
    a->lpVtbl->Release(a);
    show("A Release");
    b->lpVtbl->Release(b);
    show("B Release");
    if (keep) keep->lpVtbl->Release(keep), show("keeper Release");
    di->lpVtbl->Release(di);
    return 0;
}
