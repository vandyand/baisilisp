;; Portable clojure.tools.namespace/basilisp.tools.namespace root facade surface.
;;
;; The deprecated classpath helpers enumerate host-specific classpath/import
;; search path entries, so this fixture locks public resolution. Basilisp-local
;; tests control sys.path and exercise directory/archive behavior.

(require '[clojure.tools.namespace :as namespace])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :root-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.namespace
                                              :lpy 'basilisp.tools.namespace))
                               %)
                   '[clojure-source-file?
                     find-clojure-sources-in-dir
                     comment?
                     ns-decl?
                     read-ns-decl
                     read-file-ns-decl
                     find-ns-decls-in-dir
                     find-namespaces-in-dir
                     clojure-sources-in-jar
                     read-ns-decl-from-jarfile-entry
                     find-ns-decls-in-jarfile
                     find-namespaces-in-jarfile
                     find-ns-decls-on-classpath
                     find-namespaces-on-classpath]))
