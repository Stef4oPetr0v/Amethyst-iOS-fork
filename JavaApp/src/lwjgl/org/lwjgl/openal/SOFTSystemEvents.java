/*
 * Copyright LWJGL. All rights reserved.
 * License terms: https://www.lwjgl.org/license
 */
package org.lwjgl.openal;

import javax.annotation.*;

import java.nio.*;

import org.lwjgl.system.*;

/**
 * LWJGL 3.4 bindings to the {@code ALC_SOFT_system_events} extension, which LWJGL 3.3 lacks and Minecraft 26.1 uses to
 * track audio devices. Every event is reported as not supported, so callers fall back to polling for device changes.
 */
public class SOFTSystemEvents {

    public static final int
        ALC_EVENT_TYPE_DEFAULT_DEVICE_CHANGED_SOFT = 0x19D6,
        ALC_EVENT_TYPE_DEVICE_ADDED_SOFT           = 0x19D7,
        ALC_EVENT_TYPE_DEVICE_REMOVED_SOFT         = 0x19D8;

    public static final int
        ALC_PLAYBACK_DEVICE_SOFT = 0x19D4,
        ALC_CAPTURE_DEVICE_SOFT  = 0x19D5;

    public static final int
        ALC_EVENT_SUPPORTED_SOFT     = 0x19D9,
        ALC_EVENT_NOT_SUPPORTED_SOFT = 0x19DA;

    protected SOFTSystemEvents() {
        throw new UnsupportedOperationException();
    }

    // --- [ alcEventIsSupportedSOFT ] ---

    @NativeType("ALCenum")
    public static int alcEventIsSupportedSOFT(@NativeType("ALCenum") int eventType, @NativeType("ALCenum") int deviceType) {
        return ALC_EVENT_NOT_SUPPORTED_SOFT;
    }

    // --- [ alcEventControlSOFT ] ---

    public static boolean nalcEventControlSOFT(int count, long events, boolean enable) {
        return false;
    }

    @NativeType("ALCboolean")
    public static boolean alcEventControlSOFT(@Nullable @NativeType("ALCenum const *") IntBuffer events, @NativeType("ALCboolean") boolean enable) {
        return false;
    }

    // --- [ alcEventCallbackSOFT ] ---

    public static void nalcEventCallbackSOFT(long callback, long userParam) {
    }

    @NativeType("ALCvoid")
    public static void alcEventCallbackSOFT(@Nullable @NativeType("ALCEVENTPROCTYPESOFT") SOFTSystemEventProcI callback, @NativeType("ALCvoid *") long userParam) {
    }

    @NativeType("ALCboolean")
    public static boolean alcEventControlSOFT(@Nullable @NativeType("ALCenum const *") int[] events, @NativeType("ALCboolean") boolean enable) {
        return false;
    }

}
