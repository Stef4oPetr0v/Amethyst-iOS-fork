/*
 * Copyright LWJGL. All rights reserved.
 * License terms: https://www.lwjgl.org/license
 */
package org.lwjgl.glfw;

import javax.annotation.*;

import org.lwjgl.system.*;

import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.system.MemoryUtil.*;

/** Instances of this class may be passed to the {@link GLFW#glfwSetIMEStatusCallback SetIMEStatusCallback} method. */
public abstract class GLFWIMEStatusCallback extends Callback implements GLFWIMEStatusCallbackI {

    public static GLFWIMEStatusCallback create(long functionPointer) {
        GLFWIMEStatusCallbackI instance = Callback.get(functionPointer);
        return instance instanceof GLFWIMEStatusCallback
            ? (GLFWIMEStatusCallback)instance
            : new Container(functionPointer, instance);
    }

    @Nullable
    public static GLFWIMEStatusCallback createSafe(long functionPointer) {
        return functionPointer == NULL ? null : create(functionPointer);
    }

    public static GLFWIMEStatusCallback create(GLFWIMEStatusCallbackI instance) {
        return instance instanceof GLFWIMEStatusCallback
            ? (GLFWIMEStatusCallback)instance
            : new Container(instance.address(), instance);
    }

    protected GLFWIMEStatusCallback() {
        super(CIF);
    }

    GLFWIMEStatusCallback(long functionPointer) {
        super(functionPointer);
    }

    public GLFWIMEStatusCallback set(long window) {
        glfwSetIMEStatusCallback(window, this);
        return this;
    }

    private static final class Container extends GLFWIMEStatusCallback {

        private final GLFWIMEStatusCallbackI delegate;

        Container(long functionPointer, GLFWIMEStatusCallbackI delegate) {
            super(functionPointer);
            this.delegate = delegate;
        }

        @Override
        public void invoke(long window) {
            delegate.invoke(window);
        }

    }

}
