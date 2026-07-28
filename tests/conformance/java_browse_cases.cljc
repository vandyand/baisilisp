;; Portable clojure.java.browse/basilisp.java.browse compatibility cases.

(require '[clojure.java.browse :as browse]
         '[clojure.java.browse-ui])

#?(:lpy (import sys))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def success-script
  #?(:clj "/bin/true"
     :lpy sys/executable))

(emit-case :browse-public-surface
           [(sort (map name (keys (ns-publics 'clojure.java.browse))))
            (sort (map name (keys (ns-publics 'clojure.java.browse-ui))))])

(emit-case :open-url-script-initial-state
           @browse/*open-url-script*)

(emit-case :browse-url-script-success
           (binding [browse/*open-url-script* (atom success-script)]
             (browse/browse-url "https://example.invalid")))
