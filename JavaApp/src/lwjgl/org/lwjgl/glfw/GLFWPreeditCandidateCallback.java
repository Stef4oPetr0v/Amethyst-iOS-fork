/*
 * Copyright LWJGL. All rights reserved.
 * License terms: https://www.lwjgl.org/license
 */
package org.lwjgl.glfw;

import javax.annotation.*;

import org.lwjgl.system.*;

import static org.lwjgl.glfw.GLFW.*;
import static org.lwjgl.system.MemoryUtil.*;

/** Instances of this class may be passed to the {@link GLFW#glfwSetPreeditCandidateCallback SetPreeditCandidateCallback} method. */
public abstract class GLFWPreeditCandidateCallback extends Callback implements GLFWPreeditCandidateCallbackI {

    public static GLFWPreeditCandidateCallback create(long functionPointer) {
        GLFWPreeditCandidateCallbackI instance = Callback.get(functionPointer);
        return instance instanceof GLFWPreeditCandidateCallback
            ? (GLFWPreeditCandidateCallback)instance
            : new Container(functionPointer, instance);
    }

    @Nullable
    public static GLFWPreeditCandidateCallback createSafe(long functionPointer) {
        return functionPointer == NULL ? null : create(functionPointer);
    }

    public static GLFWPreeditCandidateCallback create(GLFWPreeditCandidateCallbackI instance) {
        return instance instanceof GLFWPreeditCandidateCallback
            ? (GLFWPreeditCandidateCallback)instance
            : new Container(instance.address(), instance);
    }

    protected GLFWPreeditCandidateCallback() {
        super(CIF);
    }

    GLFWPreeditCandidateCallback(long functionPointer) {
        super(functionPointer);
    }

    public GLFWPreeditCandidateCallback set(long window) {
        glfwSetPreeditCandidateCallback(window, this);
        return this;
    }

    private static final class Container extends GLFWPreeditCandidateCallback {

        private final GLFWPreeditCandidateCallbackI delegate;

        Container(long functionPointer, GLFWPreeditCandidateCallbackI delegate) {
            super(functionPointer);
            this.delegate = delegate;
        }

        @Override
        public void invoke(long window, int candidatesCount, int selectedIndex, int pageStart, int pageSize) {
            delegate.invoke(window, candidatesCount, selectedIndex, pageStart, pageSize);
        }

    }

}
