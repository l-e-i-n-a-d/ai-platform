package io.aiplatform.contracts;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Java half of the cross-language contract conformance check (ADR-0024, ADR-0020 §6).
 *
 * <p>Hand-written, unlike everything else in this module. It does three things and
 * prints the results as JSON for {@code .github/scripts/contract_test.py} to compare
 * against the Python half:
 *
 * <ol>
 *   <li>reports the shape of every generated type by reflection -- component names,
 *       which are required, and enum wire values;
 *   <li>round-trips every contract example through {@code fromMap} and {@code toMap};
 *   <li>reproduces the canonical form and digest of every hashing test vector.
 * </ol>
 *
 * <p>It deliberately depends on nothing outside the JDK. A JSON binding library would
 * be the obvious choice, but the point of this harness is to demonstrate that the
 * contracts are reproducible without agreeing on one -- and the canonicalisation of
 * ADR-0020 has to be implemented here anyway, since a shared library would prove only
 * that both languages call the same code, not that the specification is unambiguous.
 */
public final class ConformanceHarness {

    private ConformanceHarness() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("usage: ConformanceHarness <repository-root>");
            System.exit(2);
        }
        Path root = Path.of(args[0]);

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("types", describeTypes(root));
        report.put("examples", roundTripExamples(root));
        report.put("vectors", checkVectors(root));
        System.out.println(Json.write(report));
    }

    // -- 1. shape report --------------------------------------------------

    private static Map<String, Object> describeTypes(Path root) throws IOException {
        Map<String, Object> types = new TreeMap<>();
        Path sources = root.resolve("contracts/java/src/main/java/io/aiplatform/contracts");
        try (var stream = Files.list(sources)) {
            List<String> names = stream
                    .map(p -> p.getFileName().toString())
                    .filter(n -> n.endsWith(".java"))
                    .map(n -> n.substring(0, n.length() - ".java".length()))
                    .sorted()
                    .toList();
            for (String name : names) {
                if (name.equals("Required")) {
                    continue;
                }
                Class<?> type;
                try {
                    type = Class.forName("io.aiplatform.contracts." + name);
                } catch (ClassNotFoundException e) {
                    throw new IllegalStateException("generated source without a class: " + name, e);
                }
                if (type.isEnum()) {
                    List<String> values = new ArrayList<>();
                    for (Object constant : type.getEnumConstants()) {
                        values.add(wireOf(constant));
                    }
                    types.put(name, Map.of("kind", "enum", "values", values));
                } else if (type.isRecord()) {
                    List<String> fields = new ArrayList<>();
                    List<String> required = new ArrayList<>();
                    for (var component : type.getRecordComponents()) {
                        // Compare wire names, not Java names: a component renamed to
                        // avoid a keyword collision is still the same contract field,
                        // and comparing Java names would report a difference that does
                        // not exist on the wire.
                        Wire wire = component.getAnnotation(Wire.class);
                        String wireName = wire != null ? wire.value() : component.getName();
                        fields.add(wireName);
                        if (component.isAnnotationPresent(Required.class)) {
                            required.add(wireName);
                        }
                    }
                    required.sort(Comparator.naturalOrder());
                    types.put(name, Map.of("kind", "record", "fields", fields, "required", required));
                }
            }
        }
        return types;
    }

    private static String wireOf(Object constant) {
        try {
            return (String) constant.getClass().getMethod("wire").invoke(constant);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("generated enum without wire(): " + constant, e);
        }
    }

    // -- 2. example round trips -------------------------------------------

    private static Map<String, Object> roundTripExamples(Path root) throws Exception {
        Map<String, Object> results = new TreeMap<>();
        Path examples = root.resolve("schemas/examples");
        try (var stream = Files.list(examples)) {
            for (Path example : stream.filter(p -> p.toString().endsWith(".example.json")).sorted().toList()) {
                Map<String, Object> document = asMap(Json.read(Files.readString(example)));
                String schemaRef = (String) document.remove("$schema");
                document.remove("$comment");
                Map<String, Object> schema =
                        asMap(Json.read(Files.readString(example.getParent().resolve(schemaRef))));
                String title = (String) schema.get("title");

                Class<?> type = Class.forName("io.aiplatform.contracts." + title);
                Object parsed = type.getMethod("fromMap", Map.class).invoke(null, document);
                Object emitted = type.getMethod("toMap").invoke(parsed);

                String key = example.getFileName().toString();
                if (deepEquals(document, emitted)) {
                    results.put(key, Map.of("type", title, "roundTrip", "OK"));
                } else {
                    results.put(key, Map.of(
                            "type", title,
                            "roundTrip", "MISMATCH",
                            "expected", Json.write(document),
                            "actual", Json.write(emitted)));
                }
            }
        }
        return results;
    }

    private static boolean deepEquals(Object left, Object right) {
        if (left instanceof Map<?, ?> a && right instanceof Map<?, ?> b) {
            if (!a.keySet().equals(b.keySet())) {
                return false;
            }
            for (Object key : a.keySet()) {
                if (!deepEquals(a.get(key), b.get(key))) {
                    return false;
                }
            }
            return true;
        }
        if (left instanceof List<?> a && right instanceof List<?> b) {
            if (a.size() != b.size()) {
                return false;
            }
            for (int i = 0; i < a.size(); i++) {
                if (!deepEquals(a.get(i), b.get(i))) {
                    return false;
                }
            }
            return true;
        }
        if (left instanceof Number a && right instanceof Number b) {
            return a.toString().equals(b.toString()) || a.doubleValue() == b.doubleValue();
        }
        return java.util.Objects.equals(left, right);
    }

    // -- 3. hashing vectors ------------------------------------------------

    private static List<Object> checkVectors(Path root) throws Exception {
        Map<String, Object> suite =
                asMap(Json.read(Files.readString(root.resolve("schemas/hashing/vectors.json"))));
        List<Object> results = new ArrayList<>();
        for (Object entry : (List<?>) suite.get("vectors")) {
            Map<String, Object> vector = asMap(entry);
            List<String> excluded = new ArrayList<>();
            if (vector.get("hashExclude") instanceof List<?> raw) {
                raw.forEach(name -> excluded.add((String) name));
            }
            String canonical = Canonical.canonicalize(Canonical.stripExcluded(vector.get("input"), excluded));
            String digest = sha256(canonical);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("id", vector.get("id"));
            result.put("canonicalMatches", canonical.equals(vector.get("canonical")));
            result.put("digestMatches", digest.equals(vector.get("sha256")));
            result.put("canonical", canonical);
            result.put("sha256", digest);
            results.add(result);
        }
        return results;
    }

    private static String sha256(String text) throws NoSuchAlgorithmException {
        byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(text.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder(64);
        for (byte b : digest) {
            hex.append(Character.forDigit((b >> 4) & 0xF, 16));
            hex.append(Character.forDigit(b & 0xF, 16));
        }
        return hex.toString();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        return (Map<String, Object>) value;
    }
}
