;; Portable clojure.java.javadoc/basilisp.java.javadoc compatibility cases.

(require '[clojure.java.browse :as browse]
         '[clojure.java.javadoc :as javadoc])

#?(:lpy (import sys))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def success-script
  #?(:clj "/bin/true"
     :lpy sys/executable))

(defn state-cell [value]
  (#?(:clj ref :lpy atom) value))

(emit-case :javadoc-public-surface
           (sort (map name (keys (ns-publics 'clojure.java.javadoc)))))

(emit-case :javadoc-default-url-vars
           {:core-url? (and (string? javadoc/*core-java-api*)
                            (boolean (re-find #"https?://" javadoc/*core-java-api*)))
            :feeling-lucky-url? (and (string? javadoc/*feeling-lucky-url*)
                                     (boolean (re-find #"allinurl:" javadoc/*feeling-lucky-url*)))})

(emit-case :javadoc-registry-updates
           [(binding [javadoc/*local-javadocs* (state-cell (list))]
              (vec (javadoc/add-local-javadoc "docs/api")))
            (binding [javadoc/*remote-javadocs* (state-cell (sorted-map))]
              (javadoc/add-remote-javadoc "demo." "https://docs.example/"))])

(emit-case :javadoc-browser-delegation
           (binding [browse/*open-url-script* (atom success-script)
                     javadoc/*remote-javadocs* (state-cell (sorted-map))
                     javadoc/*feeling-lucky* true]
             (javadoc/javadoc "plain string fixture")))
