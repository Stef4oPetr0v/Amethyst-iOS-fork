/*
 * Copyright LWJGL. All rights reserved.
 * License terms: https://www.lwjgl.org/license
 */
package org.lwjgl.openal;

import javax.annotation.*;

import org.lwjgl.system.*;

import static org.lwjgl.system.MemoryUtil.*;

/** Instances of this class may be passed to the {@link SOFTSystemEvents#alcEventCallbackSOFT EventCallbackSOFT} method. */
public abstract class SOFTSystemEventProc extends Callback implements SOFTSystemEventProcI {

    public static SOFTSystemEventProc create(long functionPointer) {
        SOFTSystemEventProcI instance = Callback.get(functionPointer);
        return instance instanceof SOFTSystemEventProc
            ? (SOFTSystemEventProc)instance
            : new Container(functionPointer, instance);
    }

    @Nullable
    public static SOFTSystemEventProc createSafe(long functionPointer) {
        return functionPointer == NULL ? null : create(functionPointer);
    }

    public static SOFTSystemEventProc create(SOFTSystemEventProcI instance) {
        return instance instanceof SOFTSystemEventProc
            ? (SOFTSystemEventProc)instance
            : new Container(instance.address(), instance);
    }

    protected SOFTSystemEventProc() {
        super(CIF);
    }

    SOFTSystemEventProc(long functionPointer) {
        super(functionPointer);
    }

    private static final class Container extends SOFTSystemEventProc {

        private final SOFTSystemEventProcI delegate;

        Container(long functionPointer, SOFTSystemEventProcI delegate) {
            super(functionPointer);
            this.delegate = delegate;
        }

        @Override
        public void invoke(int eventType, int deviceType, long device, int length, long message, long userParam) {
            delegate.invoke(eventType, deviceType, device, length, message, userParam);
        }

    }

}
