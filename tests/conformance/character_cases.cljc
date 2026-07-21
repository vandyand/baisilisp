;; First-class character values must remain distinct from strings while flowing
;; through portable reader, printing, sequence, and collection operations.
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
         (pr-str {\a :char "a" :string})
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
