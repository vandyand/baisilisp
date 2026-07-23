;; Portable clojure.datafy/basilisp.datafy behavior.

#?(:clj
   (require '[clojure.datafy :as datafy]
            '[clojure.core.protocols :as protocols])
   :lpy
   (require '[basilisp.datafy :as datafy]
            '[basilisp.core.protocols :as protocols]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def datafy-obj-key :clojure.datafy/obj)
(def datafy-class-key :clojure.datafy/class)

(defrecord DatafyFixture [value]
  #?(:clj clojure.core.protocols/Datafiable
     :lpy basilisp.core.protocols/Datafiable)
  (datafy [this]
    (with-meta {:value value} {:existing true}))

  #?(:clj clojure.core.protocols/Navigable
     :lpy basilisp.core.protocols/Navigable)
  (nav [this k v]
    {:owner value :key k :value v}))

(defrecord PlainDatafyFixture [value]
  #?(:clj clojure.core.protocols/Datafiable
     :lpy basilisp.core.protocols/Datafiable)
  (datafy [_]
    [value]))

(defrecord IdentityDatafyFixture [value]
  #?(:clj clojure.core.protocols/Datafiable
     :lpy basilisp.core.protocols/Datafiable)
  (datafy [this]
    this))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn datafy-summary [source]
  (let [value (datafy/datafy source)
        m (meta value)]
    {:value value
     :existing (:existing m)
     :has-obj (contains? m datafy-obj-key)
     :obj-identical (identical? source (get m datafy-obj-key))
     :has-class (contains? m datafy-class-key)
     :has-basilisp-obj (contains? m :basilisp.datafy/obj)
     :has-basilisp-class (contains? m :basilisp.datafy/class)}))

(emit-case :public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.datafy
                                              :lpy 'basilisp.datafy))
                               %)
                   '[datafy nav]))

(emit-case :datafy-defaults
           (mapv (fn [value]
                   {:value (datafy/datafy value)
                    :datafy-identical (identical? value (datafy/datafy value))
                    :protocol-identical (identical? value (protocols/datafy value))})
                 [nil 0 "" :keyword [1 2] {:a 1} #{1 2}]))

(emit-case :datafy-provenance-metadata
           (datafy-summary (->DatafyFixture 42)))

(emit-case :datafy-adds-metadata-to-empty-meta-values
           (datafy-summary (->PlainDatafyFixture 7)))

(emit-case :datafy-keeps-identity-results-unchanged
           (let [source (->IdentityDatafyFixture 9)
                 result (datafy/datafy source)]
             {:identical (identical? source result)
              :meta (meta result)}))

(emit-case :nav-defaults
           {:map (datafy/nav {:value :x} :value :x)
            :vector (datafy/nav [:x] 0 :x)
            :set (datafy/nav #{:x} :x :x)
            :nil-rejected (rejected? #(datafy/nav nil nil :x))
            :protocol-nil-rejected (rejected? #(protocols/nav nil nil :x))})

(emit-case :nav-delegates
           {:datafy (datafy/nav (->DatafyFixture :owner) :child {:id 1})
            :protocols (protocols/nav (->DatafyFixture :owner) nil :root)})

(emit-case :generated-datafy-corpus
           (mapv (fn [value]
                   (select-keys (datafy-summary (->DatafyFixture value))
                                [:value :existing :has-obj :obj-identical
                                 :has-class :has-basilisp-obj
                                 :has-basilisp-class]))
                 [nil true false 0 1 -1 "" "abc" :kw
                  [1 2 3] {:a 1 :b [2 3]} #{:a :b}]))
