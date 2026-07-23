;; Portable clojure.spec.alpha multi-spec generation behavior.
;;
;; Raw generated examples are intentionally not compared because Clojure and
;; Basilisp use different RNG implementations. These cases lock the observable
;; semantic contract: generation enumerates multimethod branches, retags values,
;; and generated values conform to the selected branch.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as sgen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(s/def :tests.spec-multi/name string?)
(s/def :tests.spec-multi/id int?)

(defmulti event-spec :kind)
(defmethod event-spec :create [_]
  (s/keys :req-un [:tests.spec-multi/name]))
(defmethod event-spec :delete [_]
  (s/keys :req-un [:tests.spec-multi/id]))

(defn retag-generated-kind [value dispatch-value]
  (assoc value :generated-kind dispatch-value))

(defmulti event-spec-with-fn-retag :generated-kind)
(defmethod event-spec-with-fn-retag :create [_]
  (s/keys :req-un [:tests.spec-multi/name]))
(defmethod event-spec-with-fn-retag :delete [_]
  (s/keys :req-un [:tests.spec-multi/id]))

(emit-case :keyword-retag-validation
           (let [spec (s/multi-spec event-spec :kind)]
             {:valid-create? (s/valid? spec {:kind :create :name "Ada"})
              :valid-delete? (s/valid? spec {:kind :delete :id 1})
              :invalid-wrong-branch? (not (s/valid? spec {:kind :create :id 1}))
              :invalid-missing-method? (not (s/valid? spec {:kind :missing
                                                            :name "Ada"}))}))

(emit-case :keyword-retag-generation
           (let [spec (s/multi-spec event-spec :kind)
                 samples (sgen/sample (s/gen spec) 80)
                 tags (set (map :kind samples))]
             {:count (count samples)
              :every-valid? (every? #(s/valid? spec %) samples)
              :every-retagged? (every? #(contains? % :kind) samples)
              :all-branches-observed? (= #{:create :delete} tags)}))

(emit-case :function-retag-generation
           (let [spec (s/multi-spec event-spec-with-fn-retag retag-generated-kind)
                 samples (sgen/sample (s/gen spec) 80)
                 tags (set (map :generated-kind samples))]
             {:count (count samples)
              :every-valid? (every? #(s/valid? spec %) samples)
              :every-retagged? (every? #(contains? % :generated-kind) samples)
              :keyword-retag-key-absent? (every? #(not (contains? % :kind)) samples)
              :all-branches-observed? (= #{:create :delete} tags)}))
