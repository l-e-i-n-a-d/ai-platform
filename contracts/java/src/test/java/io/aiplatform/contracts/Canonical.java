package io.aiplatform.contracts;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Java implementation of the canonicalisation fixed by ADR-0020.
 *
 * <p>RFC 8785 (JCS), restricted by ADR-0020 §2 to documents containing no floating
 * point and no null. Its counterpart is {@code .github/scripts/canonical.py}; the two
 * are written independently from the ADR, and the test vectors in
 * {@code schemas/hashing/vectors.json} are what prove they agree. If this class simply
 * called the Python implementation, the vectors would demonstrate nothing.
 */
final class Canonical {

    private static final long MAX_SAFE_INTEGER = (1L << 53) - 1;

    private Canonical() {
    }

    static Object stripExcluded(Object value, List<String> excluded) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (!excluded.contains(key)) {
                    out.put(key, stripExcluded(entry.getValue(), excluded));
                }
            }
            return out;
        }
        if (value instanceof List<?> list) {
            List<Object> out = new ArrayList<>(list.size());
            for (Object item : list) {
                out.add(stripExcluded(item, excluded));
            }
            return out;
        }
        return value;
    }

    static String canonicalize(Object value) {
        StringBuilder out = new StringBuilder();
        write(value, out);
        return out.toString();
    }

    private static void write(Object value, StringBuilder out) {
        if (value == null) {
            throw new IllegalArgumentException("null is not a member of a hashed document (ADR-0020 §3)");
        }
        if (value instanceof Boolean bool) {
            out.append(bool ? "true" : "false");
            return;
        }
        if (value instanceof Double || value instanceof Float) {
            throw new IllegalArgumentException("hashed documents contain no floating point (ADR-0020 §2)");
        }
        if (value instanceof Number number) {
            long asLong = number.longValue();
            if (Math.abs(asLong) > MAX_SAFE_INTEGER) {
                throw new IllegalArgumentException("integer " + asLong + " exceeds the safe range (ADR-0020 §2)");
            }
            out.append(asLong);
            return;
        }
        if (value instanceof String string) {
            escape(string, out);
            return;
        }
        if (value instanceof List<?> list) {
            out.append('[');
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                write(list.get(i), out);
            }
            out.append(']');
            return;
        }
        if (value instanceof Map<?, ?> map) {
            List<String> keys = new ArrayList<>();
            for (Object key : map.keySet()) {
                keys.add(String.valueOf(key));
            }
            // Java's String.compareTo compares char values, which are UTF-16 code
            // units -- exactly the ordering RFC 8785 requires. This is the one place
            // where the Java implementation is simpler than the Python one, where the
            // natural ordering is by code point and is wrong.
            keys.sort(Comparator.naturalOrder());
            out.append('{');
            for (int i = 0; i < keys.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                escape(keys.get(i), out);
                out.append(':');
                write(map.get(keys.get(i)), out);
            }
            out.append('}');
            return;
        }
        throw new IllegalArgumentException("unsupported type in a hashed document: " + value.getClass());
    }

    private static void escape(String text, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\t' -> out.append("\\t");
                case '\n' -> out.append("\\n");
                case '\f' -> out.append("\\f");
                case '\r' -> out.append("\\r");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        // Everything at or above 0x20 is emitted literally, including
                        // DEL and every non-ASCII character. A generic "escape
                        // non-printable" rule would diverge here.
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }
}
