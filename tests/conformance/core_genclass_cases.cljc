;; Public clojure.genclass behavior hardening. The bundled clojure.genclass
;; implementation source is JVM-only and not requireable directly, so these
;; cases verify source-compatible public no-op behavior through clojure.core.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn eval-in-original-ns [form]
  (let [current-name (ns-name *ns*)]
    (try
      (eval form)
      (finally
        (in-ns (symbol (str current-name)))))))

(def direct-gen-class-options
  [[:name 'conformance.GeneratedBare]
   [:name 'conformance.GeneratedMain
    :main true
    :prefix "generated-"]
   [:name 'conformance.GeneratedExtends
    :extends 'Object
    :implements ['Runnable]]
   [:name 'conformance.GeneratedMethods
    :methods '[[run [] void]
               [withArgs [String int] String]]]
   [:name 'conformance.GeneratedState
    :state 'state
    :init 'init
    :post-init 'post-init
    :constructors '{[] []
                    [String] [Object]}]
   [:name 'conformance.GeneratedFactory
    :factory 'make
    :exposes '{toString exposedToString}
    :exposes-methods '{hashCode exposedHashCode}
    :impl-ns 'conformance.generated.impl
    :load-impl-ns false]])

(def ns-gen-class-forms
  ['(ns conformance.genclass.basic
     (:gen-class))
   '(ns conformance.genclass.named
     (:gen-class
      :name conformance.GeneratedNsNamed
      :main true
      :prefix "ns-generated-"))
   '(ns conformance.genclass.extended
     (:gen-class
      :name conformance.GeneratedNsExtended
      :extends Object
      :implements [Runnable]
      :methods [[run [] void]]
      :constructors {[] []}))
   '(ns conformance.genclass.factory
     (:gen-class
      :name conformance.GeneratedNsFactory
      :factory make
      :state state
      :init init
      :post-init post-init))])

(defn gen-class-result [options]
  (eval (list* 'gen-class options)))

(emit-case :gen-class-direct-option-contracts
           (mapv gen-class-result direct-gen-class-options))

(emit-case :gen-class-ns-clause-contracts
           (mapv eval-in-original-ns ns-gen-class-forms))

(emit-case :gen-class-macroexpansion-contracts
           [(boolean (:macro (meta #'gen-class)))
            (macroexpand '(gen-class :name conformance.GeneratedMacro))
            (eval '(with-loading-context
                     (gen-class :name conformance.GeneratedLoading)))])

(emit-case :gen-class-seeded-option-fuzz
           (mapv (fn [n]
                   (let [class-name (symbol (str "conformance.GeneratedSeed" n))
                         prefix (str "seed-" n "-")
                         opts (cond-> [:name class-name
                                       :prefix prefix]
                                (zero? (mod n 2))
                                (conj :main true)

                                (zero? (mod n 3))
                                (conj :methods '[[m [] Object]
                                                 [n [String] String]])

                                (zero? (mod n 4))
                                (conj :constructors '{[] []
                                                      [String] [Object]})

                                (zero? (mod n 5))
                                (conj :state 'state
                                      :init 'init
                                      :post-init 'post-init)

                                (zero? (mod n 6))
                                (conj :factory 'make
                                      :load-impl-ns false))]
                     [n (gen-class-result opts)]))
                 (range 32)))

(emit-case :gen-class-invalid-boundaries
           {:direct-invalid-name (rejected? #(gen-class :name))
            :ns-invalid-syntax (rejected? #(eval-in-original-ns
                                            '(ns conformance.genclass.invalid
                                               (:gen-class :name))))})
