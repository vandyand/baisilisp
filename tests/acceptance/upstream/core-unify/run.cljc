;; Exercise the source-level core.unify port through deterministic public and
;; upstream-derived contracts under both Clojure and Basilisp.

(load-file "tests/acceptance/upstream/core-unify/port/src/basilisp/core/unify.cljc")

(alias 'u 'basilisp.core.unify)

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(def CAPS
  #(and (symbol? %)
        #?(:clj (Character/isUpperCase (first (name %)))
           :lpy (.isupper (str (first (name %)))))))

(def garner-unifiers (var-get #'basilisp.core.unify/garner-unifiers))
(def unifier* (var-get #'basilisp.core.unify/unifier*))

(let [range-patterns [(garner-unifiers '(?x & ?y) [1 2 3])
                      (garner-unifiers '(?x ?y & ?z) [1 2 3])
                      (garner-unifiers '(?x & ?y) [1])]
      ignore-patterns [(garner-unifiers '(?x _ ?y) [1 2 3])
                       (garner-unifiers '(_ _ _) [1 2 3])
                       (garner-unifiers '(?x & _) [1 2 3])
                       (garner-unifiers '(_ & ?y) [1 2 3])]
      seeded-pairs [[['?a '?b] [1 2]]
                    [['?x '?x] ['?y '?y]]
                    [['?x '?y] ['?y '?x]]
                    [['f '?x ['h]] ['f ['h] '?y]]
                    [(array-map '?x 42 '?y 108)
                     (array-map :foo 42 :bar 108)]]]
  (println
   (pr-str
    {:lvars [(u/ignore-variable? '_)
             (u/lvar? '?x)
             (u/lvar? '_)
             (u/lvar? 'plain)
             (u/extract-lvars '[?a {:b [?c _ plain]}])
             (u/extract-lvars CAPS '[A b [C d]])]
     :wildcards [(u/wildcard? '(& ?xs))
                 (u/wildcard? '[& ?xs])
                 (u/wildcard? '(?x ?y))]
     :garner [(garner-unifiers '(a b) '(a b))
              (garner-unifiers '(?a ?b) '(1 2))
              (garner-unifiers '(?a ?a) '(1 2))
              (garner-unifiers '(f ?x ?y) '(f 1 ?y))
              (garner-unifiers CAPS '(Foo Bar) '(1 2))]
     :range range-patterns
     :ignore ignore-patterns
     :flatten [(u/flatten-bindings '{?y a ?x ?y})
               (u/flatten-bindings '{?x ?y ?z a})
               (u/flatten-bindings {'?x nil})]
     :public [(u/unify '(p ?x ?y) '(p ?y ?x))
              (u/unify '(p ?x ?y a) '(p ?y ?x ?x))
              (u/unify '(q (p ?x ?y) (p ?y ?x)) '(q ?z ?z))
              (u/unifier '(?a * ?x ** 2) '(4 * 5 ** 2))
              (u/unifier '?x 42)
              (u/unifier (hash-map 'a '?x) (hash-map 'a 2))
              (u/unifier #{'?a '?b '?c} #{2 3 4})
              (u/subst '[?a ?b] {'?a true '?b false})]
     :factory [((u/make-occurs-unify-fn CAPS) '(A B) '(1 2))
               ((u/make-occurs-unifier-fn CAPS) '(X Y a) '(Y X X))
               ((u/make-unify-fn CAPS) '(A B) '(1 2))
               ((u/make-unifier-fn CAPS) '(X Y a) '(Y X X))]
     :no-occurs [(u/unifier- '?x 42)
                 (u/unifier- (hash-map 'a '?x) (hash-map 'a 2))
                 (u/unify- '?x '?y '{?x [?y 1]})]
     :occurs-rejections [(rejected? #(u/unify '?x '(f ?x)))
                         (rejected? #(u/unify '?x '?y '{?x [?y 1]}))]
     :seeded (mapv (fn [[x y]] (garner-unifiers x y)) seeded-pairs)})))
