;; Exercise the source-level algo.monads port through deterministic public
;; contracts under both Clojure and Basilisp.

(load-file "tests/acceptance/upstream/tools-macro/port/src/basilisp/tools/macro.cljc")
(load-file "tests/acceptance/upstream/algo-monads/port/src/basilisp/algo/monads.cljc")

(alias 'm 'basilisp.algo.monads)

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(println
 (pr-str
  {:public-surface (sort (map name (keys (ns-publics 'basilisp.algo.monads))))
   :common-monads [(m/domonad m/maybe-m [a 3 b 4] (+ a b))
                   (m/domonad m/maybe-m [a 3 :when false] a)
                   (vec (m/domonad m/sequence-m
                          [a (range 2)
                           b (range 2)]
                          (+ a b)))
                   (sort (m/domonad m/set-m
                           [a #{1 2}
                            b #{1}]
                           (+ a b)))
                   (m/domonad (m/writer-m [])
                     [_ (m/write :a)
                      x (m/m-result 3)
                      _ (m/write :b)]
                     x)]
   :conditionals [(m/domonad m/maybe-m
                    [a 5
                     :let [b 6]
                     :if (= a 5)
                     :then [c 7]
                     :else [c nil]]
                    [a b c])
                  (m/domonad m/maybe-m
                    [a 5
                     :cond [(< a 1) [result "low"]
                            (< a 6) [result "mid"]
                            :else [result "high"]]]
                    result)
                  (m/domonad m/maybe-m
                    [a 5
                     :when false
                     b 6]
                    [a b])]
   :sequence-helpers (m/with-monad m/sequence-m
                       [(vec ((m/m-lift 2 vector) (range 2) (range 2)))
                        (vec (m/m-seq (repeat 3 (range 2))))
                        (vec ((m/m-chain (repeat 3 range)) 4))
                        (vec (m/m-map #(m/m-result (inc %)) [1 2 3]))
                        (vec (m/m-plus (range 2) (range 2)))])
   :maybe-helpers (m/with-monad m/maybe-m
                    [(m/m-fmap inc (m/m-result 1))
                     (m/m-join (m/m-result (m/m-result 2)))
                     (m/m-reduce + [1 2 3])
                     (m/m-reduce + 10 [1 2 3])
                     (m/m-until #(> % 4) #(m/m-result (inc %)) 1)
                     (m/m-when true (m/m-result :yes))
                     (m/m-when-not false (m/m-result :no))
                     (m/m-plus m/m-zero (m/m-result :first) (m/m-result :second))])
   :state-reader-cont [(let [f (m/domonad m/state-m
                                  [s (m/fetch-state)
                                   _ (m/set-state 9)]
                                  (inc s))]
                         (f 4))
                       (let [f (m/domonad m/state-m
                                 [old (m/fetch-val :n)
                                  _ (m/update-val :n inc)
                                  new (m/fetch-val :n)]
                                 [old new])]
                         (f {:n 3}))
                       (let [f (m/with-state-field :child
                                 (m/domonad m/state-m
                                   [old (m/fetch-state)
                                    _ (m/set-state :new)]
                                   old))]
                         (f {:child :old :other :same}))
                       ((m/domonad m/reader-m
                          [x (m/asks :x)
                           y (m/local #(assoc % :x 10) (m/asks :x))]
                          [x y])
                        {:x 3})
                       (m/run-cont (m/domonad m/cont-m
                                     [x (m/m-result 2)
                                      y (m/m-result 3)]
                                     (+ x y)))
                       (m/run-cont
                        (m/call-cc
                         (fn [exit]
                           (m/domonad m/cont-m
                             [_ (exit :escaped)]
                             :unreachable))))]
   :writer-variants [(m/domonad (m/writer-m "")
                       [_ (m/write "a")
                        _ (m/write "b")]
                       :done)
                     (m/domonad (m/writer-m '())
                       [_ (m/write :a)
                        _ (m/write :b)]
                       :done)
                     (let [value (m/domonad (m/writer-m #{})
                                   [_ (m/write :a)
                                    _ (m/write :a)]
                                   :done)]
                       [(first value) (sort (second value))])
                     (m/listen [1 [:a :b]])
                     (m/censor #(conj % :c) [1 [:a :b]])]
   :transformers [(vec (m/with-monad (m/maybe-t m/sequence-m)
                       ((m/m-lift 1 inc) [nil 1 nil 3])))
                  (vec (m/with-monad (m/sequence-t m/maybe-m)
                         (m/m-plus (m/m-result 1) (m/m-result 2))))
                  ((m/with-monad (m/maybe-t m/state-m)
                     (m/domonad
                      [x (m/m-plus (m/m-result 1) (m/m-result nil))
                       y (m/m-result 3)]
                      (+ x y)))
                   :state)]
   :boundaries [(rejected? #(eval '(m/domonad m/maybe-m [a 1 b] a)))
                (rejected? #(m/domonad (m/writer-m 0)
                              [_ (m/write :a)]
                              :done))
                (rejected? #(m/maybe-t m/maybe-m nil :invalid-choice))]}))
