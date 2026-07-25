;; Portable clojure.core proxy/interface residual semantics. Clojure creates
;; JVM proxy/interface classes while Basilisp creates Python proxy/interface
;; classes, so the fixture compares stable dispatch, mutation, rejection, and
;; reflection-shape contracts rather than host class identity.

(require '[clojure.string :as str])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(definterface FixtureDescribable
  (describe []))

(definterface FixtureJoiner
  (join [])
  (join [x])
  (join [x & more]))

#?(:lpy
   (deftype FixtureBase [value]
     FixtureDescribable
     (describe [this] (str "base:" value))))

#?(:lpy
   (deftype FixtureJoinerBase [value]
     FixtureJoiner
     (join [this] (str "zero:" value))
     (join [this x] (str "one:" value ":" x))
     (join [this x & more] (str "many:" value ":" x ":" (vec more)))))

(defprotocol FixtureProtocol
  (fixture-value [this]))

(deftype FixtureProtocolTarget [value])

(extend-type FixtureProtocolTarget
  FixtureProtocol
  (fixture-value [this]
    :extended))

(defn proxy-method-map [label]
  {"describe" (fn [_] label)})

(defn proxy-describe [p]
  #?(:clj (.describe p)
     :lpy (.describe p)))

(defn construct-describable-proxy []
  #?(:clj (let [cls (get-proxy-class FixtureDescribable)]
            (construct-proxy cls))
     :lpy (let [cls (get-proxy-class FixtureDescribable)]
            (construct-proxy cls))))

(defn gen-interface-result []
  #?(:clj (do
            (gen-interface :name fixture.GeneratedProxyInterface
                           :methods [[generatedMethod [] Object]])
            true)
     :lpy (boolean
           (gen-interface :name "GeneratedProxyInterface"
                          :methods '[(generated-method [self] nil)]))))

(defn method-signature-summary []
  #?(:clj (let [[method-name params return-type]
                (method-sig (.getMethod FixtureDescribable
                                        "describe"
                                        (make-array Class 0)))]
            [(string? (str method-name))
             (or (nil? params) (sequential? params))
             (some? return-type)])
     :lpy (let [f (fn fixture-sample [x y] x)
                [method-name params return-type] (method-sig f)]
            [(string? (str method-name))
             (or (nil? params) (sequential? params))
             (nil? return-type)])))

(defn proxy-super-result []
  #?(:clj (let [p (proxy [Object] []
                    (toString []
                      (str "proxy:" (proxy-super toString))))]
            (str/starts-with? (.toString p) "proxy:"))
     :lpy (let [p (proxy [FixtureBase] [:origin]
                    (describe []
                      (str "proxy:" (proxy-super describe))))]
            (= "proxy:base::origin" (.describe p)))))

(defn proxy-call-restores-nil-mapping-result []
  #?(:clj (let [method "toString"
                p (proxy [Object] []
                    (toString [] "override"))]
            (try
              (init-proxy p {method nil})
              (let [before (proxy-mappings p)
                    super-value (proxy-call-with-super #(.toString p) p method)
                    after (proxy-mappings p)]
                {:accepted true
                 :contains-before (contains? before method)
                 :nil-before (nil? (get before method))
                 :same-after (= before after)
                 :super-called (and (string? super-value)
                                    (not= "override" super-value))})
              (catch Throwable _
                {:accepted false})))
     :lpy (let [method "describe"
                p (proxy [FixtureBase] [:origin]
                    (describe [] "override"))]
            (try
              (init-proxy p {method nil})
              (let [before (proxy-mappings p)
                    super-value (proxy-call-with-super #(.describe p) p method)
                    after (proxy-mappings p)]
                {:accepted true
                 :contains-before (contains? before method)
                 :nil-before (nil? (get before method))
                 :same-after (= before after)
                 :super-called (= "base::origin" super-value)})
              (catch python/Exception _
                {:accepted false})))))

(defn proxy-multi-arity-dispatch-result []
  (let [p (proxy [FixtureJoiner] []
            (join
              ([] "zero")
              ([x] (str "one:" x))
              ([x & more] (str "many:" x ":" (vec more)))))]
    [(#?(:clj .join :lpy .join) p)
     (#?(:clj .join :lpy .join) p :x)]))

(emit-case :interface-generation-and-extension-contracts
           {:definterface [(some? FixtureDescribable)
                           (some? FixtureJoiner)]
            :gen-interface (gen-interface-result)
            :extend-type (fixture-value (FixtureProtocolTarget.
                                         #?(:clj 1 :lpy 1)))
            :method-sig (method-signature-summary)})

(emit-case :proxy-class-construction-and-init-contracts
           (let [cls (get-proxy-class FixtureDescribable)
                 proxy (construct-proxy cls)]
             {:class [(some? cls)
                      (identical? cls (get-proxy-class FixtureDescribable))]
             :construct [(some? proxy)
                          (boolean
                           (try
                             (some? (construct-proxy #?(:clj Object
                                                        :lpy python/object)))
                             (catch #?(:clj Throwable :lpy python/Exception) _
                               true)))]
             :init [(identical? proxy (init-proxy proxy (proxy-method-map "init")))
                     (= "init" (proxy-describe proxy))
                     (rejected? #(init-proxy #?(:clj (Object.)
                                                :lpy (python/object))
                                            {}))
                     (boolean
                      (try
                        (identical? proxy
                                    (init-proxy proxy
                                                {"describe"
                                                 (fn [_] "reinitialized")}))
                        (catch #?(:clj Throwable :lpy python/Exception) _
                          false)))]}))

(emit-case :proxy-mapping-update-and-super-contracts
           (let [proxy (construct-describable-proxy)]
             (init-proxy proxy (proxy-method-map "initial"))
             (let [initial (proxy-describe proxy)
                   mapping-keys (sort (keys (proxy-mappings proxy)))
                   update-return (update-proxy proxy (proxy-method-map "updated"))
                   updated (proxy-describe proxy)
                   valid-update? (boolean
                                  (try
                                    (identical? proxy
                                                (update-proxy
                                                 proxy
                                                 (proxy-method-map "updated-again")))
                                    (catch #?(:clj Throwable :lpy python/Exception) _
                                      false)))
                   _restore (update-proxy proxy (proxy-method-map "updated"))
                   clear-return (update-proxy proxy {"describe" nil})]
               {:initial initial
                :mapping-keys mapping-keys
                :update [(identical? proxy update-return)
                         updated
                         valid-update?]
                :clear [(identical? proxy clear-return)
                        (not= "updated"
                              (try
                                (proxy-describe proxy)
                                (catch #?(:clj Throwable :lpy python/Exception) _
                                  :rejected)))]
                :invalid-mappings (rejected? #(proxy-mappings #?(:clj (Object.)
                                                                 :lpy (python/object))))
                :proxy-super (proxy-super-result)})))

(emit-case :proxy-adversarial-restoration-and-dispatch
           {:nil-mapping-restoration (proxy-call-restores-nil-mapping-result)
            :multi-arity-dispatch (proxy-multi-arity-dispatch-result)
            :duplicate-method-rejected
            (rejected? #(eval '(proxy [FixtureDescribable] []
                                (describe [] "a")
                                (describe [] "b"))))})

(emit-case :proxy-seeded-update-fuzz
           (mapv (fn [n]
                   (let [proxy (construct-describable-proxy)
                         labels (mapv #(str "label-" n "-" %) (range 5))]
                     (init-proxy proxy (proxy-method-map (first labels)))
                     (let [seen (reduce (fn [acc label]
                                          (update-proxy proxy
                                                        (proxy-method-map label))
                                          (conj acc (proxy-describe proxy)))
                                        []
                                        labels)]
                       {:n n
                        :seen seen
                        :keys (sort (keys (proxy-mappings proxy)))})))
                 (range 6)))
