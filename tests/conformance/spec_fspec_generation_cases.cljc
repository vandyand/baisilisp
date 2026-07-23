;; Portable clojure.spec.alpha fspec generation behavior.
;;
;; Raw generated function identities and return values are intentionally not
;; compared. These cases lock the observable semantic contract: generated
;; values are invokable, valid arguments are accepted, invalid arguments are
;; rejected, return values conform, and no-args fspec generation fails clearly.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as sgen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn thrown?* [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :default Exception) _
      true)))

(emit-case :generated-fspec-callables
           (let [function-spec (s/fspec :args (s/cat :x int? :label string?)
                                        :ret boolean?)
                 generated (sgen/sample (s/gen function-spec) 30)
                 returns (map #(% 1 "ok") generated)]
             {:count (count generated)
              :every-invokable? (every? ifn? generated)
              :every-valid-fspec? (every? #(s/valid? function-spec %) generated)
              :every-return-valid? (every? boolean? returns)
              :invalid-args-rejected? (every? #(thrown?* (fn [] (% "bad" "ok")))
                                              generated)
              :invalid-arity-rejected? (every? #(thrown?* (fn [] (% 1)))
                                               generated)}))

(emit-case :generated-fspec-fn-relation-sees-conformed-args
           (let [function-spec (s/fspec :args (s/cat :x int?)
                                        :ret int?
                                        :fn (fn [{:keys [args ret]}]
                                              (and (map? args)
                                                   (contains? args :x)
                                                   (integer? ret))))
                 generated (first (sgen/sample (s/gen function-spec) 1))
                 returns (map generated (range 30))]
             {:every-return-valid? (every? int? returns)
              :invalid-args-rejected? (thrown?* (fn [] (generated "bad")))}))

(emit-case :fspec-without-args-is-not-generatable
           {:ret-only-rejected?
            (thrown?* (fn []
                        (sgen/generate
                         (s/gen (s/fspec :ret int?)))))})
