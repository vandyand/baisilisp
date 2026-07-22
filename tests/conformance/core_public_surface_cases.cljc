;; Portable checks for the final clojure.core public names Basilisp previously
;; lacked. These names are mostly JVM compiler/classloader controls, so the
;; contract here is source compatibility: public resolution, bindability where
;; Clojure exposes Vars, the Java primitive-name table shape, and honest no-op
;; macro behavior on Python.

(ns conformance.core-public-surface-cases
  (:gen-class))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def compat-names
  ["*fn-loader*"
   "*unchecked-math*"
   "*use-context-classloader*"
   "gen-class"
   "primitives-classnames"
   "with-loading-context"])

(defn public-status [name]
  (let [v (resolve (symbol name))]
    {:resolved? (boolean v)
     :macro? (boolean (:macro (meta v)))
     :bound? (boolean (and v (bound? v)))}))

(emit-case :compat-name-status
           (into {}
                 (map (fn [name] [name (public-status name)]))
                 compat-names))

(emit-case :compat-defaults
           {:fn-loader *fn-loader*
            :unchecked-math *unchecked-math*
            :use-context-classloader *use-context-classloader*
            :primitives-classnames primitives-classnames})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(def unchecked-values
  [false true :warn-on-boxed])

(defn seeded-binding-case [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)
        loader (symbol (str "loader-" (mod s1 17)))
        unchecked (nth unchecked-values (mod s2 (count unchecked-values)))
        use-context? (zero? (mod s3 2))]
    (binding [*fn-loader* loader
              *unchecked-math* unchecked
              *use-context-classloader* use-context?]
      [*fn-loader* *unchecked-math* *use-context-classloader*])))

(emit-case :seeded-binding-fuzz
           (loop [remaining 64
                  seed 324508639
                  results []]
             (if (zero? remaining)
               results
               (let [next (next-seed seed)]
                 (recur (dec remaining)
                        next
                        (conj results (seeded-binding-case next)))))))

(defn nested-loading [n value]
  (if (zero? n)
    value
    (with-loading-context
      (nested-loading (dec n) value))))

(emit-case :loading-context-stress
           {:empty (with-loading-context)
            :single (with-loading-context :ok)
            :nested (nested-loading 48 :done)
            :side-effects (let [a (atom [])]
                            (dotimes [n 32]
                              (with-loading-context
                                (swap! a conj n)))
                            @a)})

(emit-case :gen-class-adversarial-noops
           [(gen-class :name conformance.Generated0)
            (gen-class :name "conformance.Generated1"
                       :main true
                       :prefix "generated-")
            (gen-class :name conformance.Generated2
                       :methods [[m [] Object]
                                 [withArgs [String int] String]])
            (gen-class :name conformance.Generated3
                       :state state
                       :init init
                       :post-init post-init
                       :constructors {[] []})])
