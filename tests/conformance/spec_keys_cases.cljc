;; Portable clojure.spec.alpha keys semantic cases, especially :req-un/:opt-un.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as sgen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(s/def :tests.spec-keys/name string?)
(s/def :tests.spec-keys/age int?)
(s/def :tests.spec-keys/email string?)

(def qualified-person
  (s/keys :req [:tests.spec-keys/name]
          :opt [:tests.spec-keys/age]))

(def unqualified-person
  (s/keys :req-un [:tests.spec-keys/name]
          :opt-un [:tests.spec-keys/age :tests.spec-keys/email]))

(def mixed-person
  (s/keys :req [:tests.spec-keys/name]
          :req-un [:tests.spec-keys/age]))

(emit-case :qualified-and-unqualified-presence
           {:qualified-valid? (s/valid? qualified-person
                                        {:tests.spec-keys/name "Ada"})
            :qualified-missing? (s/valid? qualified-person
                                          {:name "Ada"})
            :unqualified-valid? (s/valid? unqualified-person
                                          {:name "Ada"})
            :unqualified-qualified-key? (s/valid? unqualified-person
                                                  {:tests.spec-keys/name "Ada"})
            :mixed-valid? (s/valid? mixed-person
                                    {:tests.spec-keys/name "Ada"
                                     :age 42})})

(emit-case :unqualified-value-validation
           {:valid? (s/valid? unqualified-person
                              {:name "Ada" :age 42 :email "ada@example.test"})
            :invalid? (s/invalid? (s/conform unqualified-person {:name 1}))
            :conform (s/conform unqualified-person {:name "Ada" :age 42})
            :problem (let [p (first (::s/problems
                                      (s/explain-data unqualified-person
                                                      {:name 1})))]
                       {:path (:path p)
                        :in (:in p)
                        :via (:via p)
                        :val (:val p)})})

(emit-case :unqualified-form-and-describe
           {:form (s/form unqualified-person)
            :describe (s/describe unqualified-person)})

(emit-case :unqualified-generation-shape
           (let [samples (sgen/sample (s/gen unqualified-person) 30)]
             {:every-valid? (every? #(s/valid? unqualified-person %) samples)
              :all-required? (every? #(contains? % :name) samples)
              :no-qualified-required? (every? #(not (contains?
                                                     %
                                                     :tests.spec-keys/name))
                                              samples)}))

(def key-value-options
  (s/keys* :req-un [:tests.spec-keys/name]
           :opt-un [:tests.spec-keys/age]))

(emit-case :keys-star-sequence-semantics
           (let [cat-result (s/conform (s/cat :opts key-value-options
                                              :tail string?)
                                       [:name "Ada" "done"])]
             {:regex? (boolean (s/regex? key-value-options))
              :valid? (s/valid? key-value-options [:name "Ada"])
              :map-invalid? (s/invalid? (s/conform key-value-options
                                                   [{:name "Ada"}]))
              :conform-ok? (= {:name "Ada" :age 42}
                              (s/conform key-value-options
                                         [:name "Ada" :age 42]))
              :unform (vec (s/unform key-value-options {:name "Ada"}))
              :cat-ok? (and (= {:name "Ada"} (:opts cat-result))
                            (= "done" (:tail cat-result)))}))

(emit-case :keys-star-generation-shape
           (let [samples (sgen/sample (s/gen key-value-options) 30)]
             {:every-valid? (every? #(s/valid? key-value-options %) samples)
              :even-counts? (every? #(even? (count %)) samples)
              :all-required? (every? #(contains? (apply hash-map %) :name)
                                     samples)}))
