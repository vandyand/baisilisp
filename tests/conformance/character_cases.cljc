;; First-class character values must remain distinct from strings while flowing
;; through portable reader, printing, sequence, and collection operations.
(defn rejected? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(doseq [value
        [(pr-str \a)
         (pr-str \space)
         (pr-str \newline)
         (= \a "a")
         (char? \a)
         (string? \a)
         (int \Z)
         (str \Z)
         (pr-str (vec "aZ"))
         (pr-str (set "aba"))
         (let [m {\a :char "a" :string}]
           {:char-value? (= :char (get m \a))
            :string-value? (= :string (get m "a"))
            :distinct-keys? (= 2 (count m))})
         (pr-str [(first "aZ") (nth "aZ" 1) (get "aZ" 0)])]]
  (prn value))

;; Clojure strings are indexed by JVM UTF-16 code units. Render the characters
;; as integers so isolated surrogate units never need to cross a text stream.
(let [s "a😀𝄞b"]
  (prn {:utf16-count (count s)
        :utf16-units (mapv int s)
        :utf16-vector (mapv int (vec s))
        :utf16-nth [(int (nth s 1)) (int (get s 2))]
        :utf16-subs [(mapv int (subs s 1 3))
                     (mapv int (subs s 1 2))
                     (mapv int (subs s 2 3))]
        :negative [(nth s -1 :not-found)
                   (get s -1 :not-found)
                   (contains? s -1)]
        :char-coercion [(int (char 65535))
                         (int (unchecked-char 65536))
                         (int (unchecked-char -1))]
        :char-array (mapv int (char-array s))}))

(let [s "a😀𝄞b"]
  (prn {:case :residual-subs-boundaries
        :value {:valid [(mapv int (subs s 0))
                        (mapv int (subs s 0 0))
                        (mapv int (subs s 1 3))
                        (mapv int (subs s 3 6))
                        (mapv int (subs s 6 6))]
                :invalid [(rejected? #(subs s -1))
                          (rejected? #(subs s 0 7))
                          (rejected? #(subs s 3 2))
                          (rejected? #(subs s nil))
                          (rejected? #(subs s 1 nil))
                          (rejected? #(subs s true))
                          (rejected? #(subs s 1 false))
                          (rejected? #(subs s 1.0))
                          (rejected? #(subs nil 0))
                          (rejected? #(subs 123 0))]}}))

;; The upstream residual suite still contains old Basilisp expectations where a
;; character acts like a one-character Python string. JVM Clojure treats a
;; character as a scalar value, not as a seqable collection.
(prn {:case :residual-character-scalar-collection-boundaries
      :value {:predicates [(char? \a)
                           (string? \a)
                           (seqable? \a)
                           (seqable? "a")]
              :collection-rejections [(rejected? #(seq \a))
                                      (rejected? #(empty? \a))
                                      (rejected? #(not-empty \a))
                                      (rejected? #(fnext \a))
                                      (rejected? #(last \a))
                                      (rejected? #(vec (remove identity \a)))
                                      (rejected? #(vec (reverse \a)))
                                      (rejected? #(set \a))]
              :string-counterparts [(mapv str (seq "a"))
                                    (empty? "")
                                    (not-empty "a")
                                    (fnext "ab")
                                    (last "ab")
                                    (mapv str (remove #{\a} "aba"))
                                    (mapv str (reverse "ab"))
                                    (set "aba")]
              :string-reduction-character-preservation
              [(mapv int (into [] "abΩ"))
               (mapv char? (into [] "abΩ"))
               (mapv int (persistent! (reduce conj! (transient []) "abΩ")))
               (mapv char? (persistent! (reduce conj! (transient []) "abΩ")))]}})

(prn {:case :seeded-character-scalar-residual-corpus
      :value (mapv (fn [code]
                     (let [c (char code)
                           s (str c)]
                       {:code (int c)
                        :print (if (< code 128) (pr-str c) :non-ascii)
                        :distinct-from-string (not= c s)
                        :string-units (mapv int s)
                        :predicates [(char? c) (string? c) (seqable? c)]
                        :collection-rejections [(rejected? #(seq c))
                                                (rejected? #(empty? c))
                                                (rejected? #(not-empty c))
                                                (rejected? #(fnext c))
                                                (rejected? #(last c))
                                                (rejected? #(vec (remove identity c)))
                                                (rejected? #(vec (reverse c)))
                                                (rejected? #(set c))]
                        :map-keys [(get {c :char s :string} c)
                                   (get {c :char s :string} s)
                                   (count {c :char s :string})]}))
                   [8 9 10 12 13 32 65 90 91 92 937 65535])})
