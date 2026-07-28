;; Portable clojure.core definition-form and utility residual semantics.
;; Host-specific type, lock, method, and URI objects are normalized to data
;; before comparison.

#?(:clj (import 'java.net.URI)
   :lpy (import [urllib.parse :as urlparse]
                threading))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(declare declared-empty declared-filled)
(def declared-filled 42)

(defn- private-helper [x]
  (+ x 1))

(defstruct fixture-struct :a :b)

(defrecord UtilityRecord [a])

(emit-case :definition-form-contracts
           {:declare [(var? #'declared-empty)
                      (bound? #'declared-empty)
                      (var? #'declared-filled)
                      (bound? #'declared-filled)
                      declared-filled]
            :defn- [(private-helper 4)
                    (true? (:private (meta #'private-helper)))]
            :defstruct [(into (sorted-map) (struct fixture-struct 1 2))
                        (into (sorted-map) (struct-map fixture-struct
                                                       :b 20
                                                       :a 10))]})

(emit-case :local-definition-and-destructure-contracts
           {:letfn (letfn [(evenish? [n]
                             (if (zero? n)
                               true
                               (oddish? (dec n))))
                           (oddish? [n]
                             (if (zero? n)
                               false
                               (evenish? (dec n))))]
                    (mapv evenish? (range 7)))
            :destructure (let [bindings (destructure
                                          '[[a b & more :as all] [1 2 3 4]
                                            {:keys [x y] :or {y 9} :as m} {:x 1}])
                               result (eval (list 'let bindings
                                                  '[a b more all x y m]))]
                           [(vector? bindings)
                            (even? (count bindings))
                            result])
            :memfn #?(:clj ((memfn toUpperCase) "abc")
                      :lpy ((memfn upper) "abc"))})

(emit-case :utility-boundary-contracts
           (let [memo-calls (atom 0)
                 memo-f (memoize (fn [& xs]
                                   (swap! memo-calls inc)
                                   (vec xs)))
                 timed-value (atom nil)
                 timed-out (with-out-str
                             (reset! timed-value (time (+ 1 2))))
                 lock-value (atom 0)]
             {:memoize [(memo-f 1 2)
                        (memo-f 1 2)
                        (memo-f nil false)
                        (memo-f nil false)
                        @memo-calls]
              :gensym (let [a (gensym)
                            b (gensym "prefix")]
                        [(symbol? a)
                         (nil? (namespace a))
                         (not= a b)
                         (boolean (re-find #"^prefix" (name b)))])
              :time [@timed-value
                     (boolean (re-find #"msecs" timed-out))]
              :locking (locking #?(:clj (Object.)
                                   :lpy (threading/RLock))
                         (swap! lock-value inc)
                         @lock-value)
              :io! (nil? (io!))}))

(emit-case :hash-helper-contracts
           {:hash-combine (hash-combine 1 2)
            :mix-collection-hash (mix-collection-hash 3 2)
            :hash-ordered [(hash-ordered-coll [1 2 3])
                           (= (hash-ordered-coll [1 2 3])
                              (hash-ordered-coll '(1 2 3)))]
            :hash-unordered [(hash-unordered-coll #{1 2 3})
                             (= (hash-unordered-coll #{1 2 3})
                                (hash-unordered-coll [3 2 1]))]})

(emit-case :portable-type-and-string-helper-contracts
           {:class [(true? #?(:clj (= String (class "x"))
                              :lpy (= python/str (class "x"))))
                    (true? #?(:clj (= Long (class 1))
                              :lpy (= python/int (class 1))))]
            :type [(true? #?(:clj (= String (type "x"))
                             :lpy (= python/str (type "x"))))
                   (true? #?(:clj (= Long (type 1))
                             :lpy (= python/int (type 1))))]
            :cast [(= "x" #?(:clj (cast String "x")
                             :lpy (cast python/str "x")))
                   (nil? #?(:clj (cast String nil)
                            :lpy (cast python/str nil)))
                   (rejected? #(do #?(:clj (cast Long "x")
                                      :lpy (cast python/int "x"))))]
            :find-keyword (let [present (keyword "core-definition-utility" "present")]
                            [present
                             (find-keyword "core-definition-utility" "present")
                             (find-keyword "core-definition-utility" "missing")])
            :chars [(char-escape-string \newline)
                    (char-escape-string \x)
                    (char-name-string \space)
                    (char-name-string \x)]
            :record [(record? (->UtilityRecord 1))
                     (record? {:a 1})]
            :uri [(true? #?(:clj (uri? (URI. "https://example.test/path?q=1"))
                            :lpy (uri? (urlparse/urlparse
                                        "https://example.test/path?q=1"))))
                  (uri? "https://example.test/path?q=1")]
            :inst-ms (inst-ms* #inst "1970-01-01T00:00:01.234Z")
            :unchecked-double [(double? (unchecked-double 1))
                               (unchecked-double 1.5)]})
