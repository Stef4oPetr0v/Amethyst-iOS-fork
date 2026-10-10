/*
 * Copyright LWJGL. All rights reserved.
 * License terms: https://www.lwjgl.org/license
 */
package org.lwjgl.glfw;

import javax.annotation.*;

import org.lwjgl.system.*;

import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.system.MemoryUtil.*;

/** Instances of this class may be passed to the {@link GLFW#glfwSetPreeditCallback SetPreeditCallback} method. */
public abstract class GLFWPreeditCallback extends Callback implements GLFWPreeditCallbackI {

    public static GLFWPreeditCallback create(long functionPointer) {
        GLFWPreeditCallbackI instance = Callback.get(functionPointer);
        return instance instanceof GLFWPreeditCallback
            ? (GLFWPreeditCallback)instance
            : new Container(functionPointer, instance);
    }

    @Nullable
    public static GLFWPreeditCallback createSafe(long functionPointer) {
        return functionPointer == NULL ? null : create(functionPointer);
    }

    public static GLFWPreeditCallback create(GLFWPreeditCallbackI instance) {
        return instance instanceof GLFWPreeditCallback
            ? (GLFWPreeditCallback)instance
            : new Container(instance.address(), instance);
    }

    protected GLFWPreeditCallback() {
        super(CIF);
    }

    GLFWPreeditCallback(long functionPointer) {
        super(functionPointer);
    }

    public GLFWPreeditCallback set(long window) {
        glfwSetPreeditCallback(window, this);
        return this;
    }

    private static final class Container extends GLFWPreeditCallback {

        private final GLFWPreeditCallbackI delegate;

        Container(long functionPointer, GLFWPreeditCallbackI delegate) {
            super(functionPointer);
            this.delegate = delegate;
        }

        @Override
        public void invoke(long window, int preeditCount, long preeditString, int blockCount, long blockSizes, int focusedBlock, int caret) {
            delegate.invoke(window, preeditCount, preeditString, blockCount, blockSizes, focusedBlock, caret);
        }

    }

}
