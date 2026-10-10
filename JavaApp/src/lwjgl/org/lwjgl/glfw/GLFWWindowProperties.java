package org.lwjgl.glfw;

import java.util.*;
import net.kdt.pojavlaunch.Tools;

public class GLFWWindowProperties {
    public int width, height;
    public float x, y;
    public CharSequence title;
    public boolean shouldClose, isInitialSizeCalled, isCursorEntered;
    public long monitor;
    public Map<Integer, Integer> inputModes = new HashMap<>();
    public Map<Integer, Integer> windowAttribs = new HashMap<>();

    {
        // glfwGetInputMode() fails on modes that were never set; Amethyst-Android also defaults this one
        inputModes.put(GLFW.GLFW_IME, GLFW.GLFW_FALSE);
    }
    
    @Override
    public String toString() {
        return "width=" + width + ", " +
          "height=" + height + ", " +
          "x=" + x + ", " +
          "y=" + y + ", ";
    }
}
