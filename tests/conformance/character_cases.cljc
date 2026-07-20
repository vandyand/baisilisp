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
