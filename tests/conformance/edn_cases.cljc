;; Portable clojure.edn/basilisp.edn conformance cases. Clojure's public EDN
;; namespace only exposes read/read-string, so writer round-trips are covered
;; locally in Basilisp tests while this fixture locks shared reader semantics.

#?(:clj (require '[clojure.edn :as edn])
   :lpy (require '[basilisp.edn :as edn]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn read-stream [opts source]
  #?(:clj (edn/read opts (java.io.PushbackReader. (java.io.StringReader. source)))
     :lpy (edn/read (io/StringIO source) opts)))

(defn generated-scalar [seed]
  (case (mod seed 10)
    0 (str seed)
    1 (str "-" seed)
    2 (str "\"" "s" seed "\\n" "x" "\"")
    3 (str ":kw" seed)
    4 (str "sym" seed)
    5 "nil"
    6 "true"
    7 "false"
    8 (str "\\" (char (+ 65 (mod seed 26))))
    (str seed "/" (inc (mod seed 17)))))

(defn generated-form [depth seed]
  (if (zero? depth)
    (generated-scalar seed)
    (case (mod (+ depth seed) 5)
      0 (str "[" (generated-form (dec depth) (+ seed 1))
             " " (generated-form (dec depth) (+ seed 2)) "]")
      1 (str "(" (generated-form (dec depth) (+ seed 1))
             " " (generated-form (dec depth) (+ seed 2)) ")")
      2 (str "{:a" seed " " (generated-form (dec depth) (+ seed 1))
             " :b" seed " " (generated-form (dec depth) (+ seed 2)) "}")
      3 (str "#{" (generated-scalar (+ seed 1))
             " " (generated-scalar (+ seed 2)) "}")
      (str "#:ns" seed "{:a " (generated-form (dec depth) (+ seed 1))
           " :b " (generated-form (dec depth) (+ seed 2)) "}"))))

(emit-case :public-surface
           (let [publics (set (map name (keys (ns-publics #?(:clj 'clojure.edn
                                                             :lpy 'basilisp.edn)))))]
             {:required-present (mapv #(contains? publics %) ["read" "read-string"])}))

(emit-case :read-string-basics
           {:nil-input (edn/read-string nil)
            :empty (edn/read-string "")
            :whitespace (edn/read-string " \n\t ")
            :eof-option (edn/read-string {:eof :done} "")
            :trailing-forms (edn/read-string "1 2")
            :line-comment (edn/read-string ";; ignored\n:a")
            :discard (edn/read-string "[1 #_2 3]")
            :nested {:list (edn/read-string "(:a [1 2] {:b #{3 4}})")
                     :namespaced-map (edn/read-string "#:acct{:id 1 :name \"Ada\"}")
                     :reader-constants [(edn/read-string "##Inf")
                                        (edn/read-string "##-Inf")
                                        (edn/read-string "##NaN")]}})

(emit-case :numbers-symbols-keywords-and-chars
           {:integers [(edn/read-string "0")
                       (edn/read-string "-42")
                       (edn/read-string "052")
                       (edn/read-string "0x2a")
                       (edn/read-string "2r101010")]
            :ratio (edn/read-string "22/7")
            :float (edn/read-string "-3.5e2")
            :symbols [(edn/read-string "sym")
                      (edn/read-string "ns/sym")
                      (edn/read-string "/")
                      (edn/read-string "+")
                      (edn/read-string "foo//")]
            :keywords [(edn/read-string ":kw")
                       (edn/read-string ":ns/kw")
                       (edn/read-string ":/")]
            :chars [(edn/read-string "\\space")
                    (edn/read-string "\\newline")
                    (edn/read-string "\\A")]})

(emit-case :tagged-readers-and-stream-read
           {:inst (inst-ms (edn/read-string "#inst \"2010-01-01T01:01:01.001-01:01\""))
            :uuid (str (edn/read-string "#uuid \"4ba98ef0-0620-4966-af61-f0f6c2dbf230\""))
            :custom-reader (edn/read-string {:readers {'fixture/box (fn [v] [:box v])}}
                                            "#fixture/box {:a 1}")
            :default-reader (edn/read-string {:default (fn [tag v] [:default tag v])}
                                             "#fixture/missing [1 2]")
            :stream-basic (read-stream {} ";;x\n[1 2]")
            :stream-eof (read-stream {:eof :done} "")})

(emit-case :rejection-boundaries
           {:invalid-number (rejected? #(edn/read-string "08"))
            :invalid-ratio (rejected? #(edn/read-string "1/0"))
            :duplicate-map-key (rejected? #(edn/read-string "{:a 1 :a 2}"))
            :duplicate-set-value (rejected? #(edn/read-string "#{:a :a}"))
            :invalid-keyword (rejected? #(edn/read-string "://"))
            :auto-resolved-keyword (rejected? #(edn/read-string "::x"))
            :unclosed-string (rejected? #(edn/read-string "\"abc"))
            :bad-string-escape (rejected? #(edn/read-string "\"\\q\""))
            :unknown-tag (rejected? #(edn/read-string "#fixture/missing [1]"))
            :bad-inst (rejected? #(edn/read-string "#inst \"bad\""))
            :bad-uuid (rejected? #(edn/read-string "#uuid \"bad\""))
            :unmatched-delimiter (rejected? #(edn/read-string "]"))})

(emit-case :generated-read-corpus
           (mapv (fn [seed]
                   (let [source (generated-form 4 seed)
                         value (edn/read-string source)]
                     {:seed seed
                      :source source
                      :value value
                      :first-only (edn/read-string (str source " :trailing"))}))
                 (range 96)))
