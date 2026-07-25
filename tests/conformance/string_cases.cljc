;; Portable clojure.string/basilisp.string public surface and semantic cases.
;; This fixture focuses on the Clojure-compatible namespace contract; Basilisp's
;; extra Python-native string helpers are covered by local tests.

(require '[clojure.string :as str])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.string
                                              :lpy 'basilisp.string))
                               %)
                   '[blank?
                     capitalize
                     ends-with?
                     escape
                     includes?
                     index-of
                     join
                     last-index-of
                     lower-case
                     re-quote-replacement
                     replace
                     replace-first
                     reverse
                     split
                     split-lines
                     starts-with?
                     trim
                     trim-newline
                     triml
                     trimr
                     upper-case]))

(emit-case :basic-predicates-and-case
           {:blank [(str/blank? nil)
                    (str/blank? "")
                    (str/blank? " \t\n")
                    (str/blank? "x")]
            :case [(str/capitalize "hELLO")
                   (str/lower-case "ABC")
                   (str/upper-case "abc")]
            :predicates [(str/starts-with? "alpha" "al")
                         (str/ends-with? "alpha" "ha")
                         (str/includes? "alpha" "ph")]
            :join [(str/join [1 :a nil])
                   (str/join "," [1 :a nil])]
            :reverse (str/reverse "abc")})

(emit-case :trim-contracts
           {:trim [(str/trim " \talpha\n")
                   (str/triml "  a  ")
                   (str/trimr "  a  ")]
            :newline (mapv str/trim-newline
                           [""
                            "\n"
                            "\r"
                            "\r\n"
                            "alpha\n"
                            "alpha\r\n"
                            "alpha\n\n"
                            "alpha\r\r"
                            "alpha\n\r"
                            "alpha\t "
                            "alpha \n beta"])})

#?(:lpy
   (emit-case :basilisp-extension-string-helpers
              {:predicates [(str/alpha? "abc")
                            (str/alpha? "abc1")
                            (str/alphanumeric? "abc1")
                            (str/alphanumeric? "abc!")
                            (str/digits? "123")
                            (str/digits? "12a")]
               :case [(str/title-case "hELLO wORLD")]
               :pad [(str/lpad "x" 4)
                     (str/lpad "x" 4 "0")
                     (str/rpad "x" 4)
                     (str/rpad "x" 4 "0")]
               :trim [(str/ltrim "  x  ")
                      (str/rtrim "  x  ")
                      (str/trim-newlines "x\r\n\n")]})
   :clj
   (emit-case :basilisp-extension-string-helpers
              {:predicates [true false true false true false]
               :case ["Hello World"]
               :pad ["   x" "000x" "x   " "x000"]
               :trim ["x  " "  x" "x"]}))

(emit-case :index-contracts
           {:index [(str/index-of "ababa" "ba")
                    (str/index-of "ababa" "ba" 2)
                    (str/index-of "ababa" "z")]
            :last [(str/last-index-of "ababa" "ba")
                   (str/last-index-of "ababa" "ba" 3)
                   (str/last-index-of "ababa" "ba" 2)
                   (str/last-index-of "ababa" "z")]})

(emit-case :split-contracts
           {:regex [(str/split "a,b," #",")
                    (str/split "a,b," #"," 0)
                    (str/split "a,b," #"," 2)
                    (str/split "a--b--" #"--")]
            :empty-regex [(str/split "abc" #"")
                          (str/split "abc" #"" 2)
                          (str/split "" #"")]
            :lines (str/split-lines "a\nb\r\nc\r")})

(emit-case :replace-contracts
           {:literal (str/replace "a.b.a" "." "!")
            :regex (str/replace "a1b22" #"\d+" "#")
            :regex-fn (str/replace "a1b22" #"\d+" #(str "[" % "]"))
            :regex-group (str/replace "a1 b22" #"([a-z])(\d+)" "$2:$1")
            :first [(str/replace-first "a1b22" #"\d+" "#")
                    (str/replace-first "a.b.a" "." "!")]
            :escape (str/escape "abca" {\a "A" \b 3 \c nil})
            :quote (str/replace "a$b" #"\$" (str/re-quote-replacement "$"))})
