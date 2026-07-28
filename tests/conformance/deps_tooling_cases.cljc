;; Portable dependency-tooling namespace compatibility cases.

(require '[clojure.java.basis :as basis]
         '[clojure.java.basis.impl :as basis-impl]
         '[clojure.repl.deps :as repl-deps]
         '[clojure.tools.deps.interop :as interop])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn thrown-message [f]
  (try
    (f)
    :ok
    (catch #?(:clj Throwable :lpy python/Exception) e
      (ex-message e))))

(emit-case :deps-tooling-public-surfaces
           [(sort (map name (keys (ns-publics 'clojure.java.basis))))
            (sort (map name (keys (ns-publics 'clojure.java.basis.impl))))
            (sort (map name (keys (ns-publics 'clojure.repl.deps))))
            (sort (map name (keys (ns-publics 'clojure.tools.deps.interop))))])

(emit-case :basis-initial-state
           [(= (basis/initial-basis) @basis-impl/init-basis)
            (= (basis/current-basis) @@basis-impl/the-basis)
            (or (nil? (basis/initial-basis))
                (map? (basis/initial-basis)))
            (or (nil? (basis/current-basis))
                (map? (basis/current-basis)))])

(emit-case :basis-update
           [(basis-impl/update-basis!
             (fn [_] {:libs {'demo/lib {:mvn/version "1"}}}))
            (basis/current-basis)
            (basis-impl/update-basis! assoc :paths ["src"])
            (basis/current-basis)])

(emit-case :interop-validation
           [(thrown-message #(interop/invoke-tool {}))
            (thrown-message #(interop/invoke-tool {:tool-name "demo" :fn :bad}))
            (thrown-message #(interop/invoke-tool {:tool-name "demo"}))])

(emit-case :repl-deps-repl-guard
           [(binding [*repl* false]
              (thrown-message #(repl-deps/add-libs {})))
            (binding [*repl* false]
              (thrown-message #(repl-deps/add-lib 'demo/lib {:mvn/version "1"})))
            (binding [*repl* false]
              (thrown-message #(repl-deps/sync-deps)))])
