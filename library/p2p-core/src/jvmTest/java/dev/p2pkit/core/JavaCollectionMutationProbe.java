package dev.p2pkit.core;

import java.util.Collection;
import java.util.Map;

final class JavaCollectionMutationProbe {
    private JavaCollectionMutationProbe() {}

    @SuppressWarnings({"rawtypes", "unchecked"})
    static boolean addFails(Collection collection, Object value) {
        try {
            collection.add(value);
            return false;
        } catch (UnsupportedOperationException expected) {
            return true;
        }
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    static boolean putFails(Map map, Object key, Object value) {
        try {
            map.put(key, value);
            return false;
        } catch (UnsupportedOperationException expected) {
            return true;
        }
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    static boolean entryMutationFails(Map map, Object value) {
        try {
            Map.Entry entry = (Map.Entry) map.entrySet().iterator().next();
            entry.setValue(value);
            return false;
        } catch (UnsupportedOperationException expected) {
            return true;
        }
    }
}
