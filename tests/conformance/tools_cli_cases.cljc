;; Portable clojure.tools.cli/basilisp.tools.cli semantic conformance.
;;
;; The fixture covers the complete public surface directly. It avoids host
;; exception strings and terminal-specific concerns, comparing only parsed data,
;; deterministic summaries, and formatted rows.

(require '[clojure.string :as str]
         '[clojure.tools.cli :as cli])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn errors? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn parsed [args specs & opts]
  (select-keys (apply cli/parse-opts args specs opts)
               [:options :arguments :errors :summary]))

(def option-specs
  [["-a" "--alpha" "Alpha flag"]
   ["-b" "--beta VALUE" "Beta value"
    :default "default"
    :validate [seq "Beta must not be blank"]]
   ["-v" "--verbose" "Verbosity"
    :default 0
    :update-fn inc]
   [nil "--[no-]daemon" "Daemon mode"
    :default true]
   ["-f" "--file NAME" "File path"
    :default []
    :update-fn conj
    :multi true]])

(def compiled-summary-specs
  [{:short-opt "-a"
    :long-opt "--alpha"
    :desc "Alpha flag"}
   {:short-opt "-b"
    :long-opt "--beta"
    :required "VALUE"
    :desc "Beta value"
    :default "default"}
   {:long-opt "--[no-]daemon"
    :desc "Daemon mode"
    :default true}])

(emit-case :tools-cli-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.cli
                                              :lpy 'basilisp.tools.cli))
                               %)
                   '[cli
                     format-lines
                     get-default-options
                     make-summary-part
                     parse-opts
                     summarize]))

(emit-case :parse-opts-success-paths
           (let [basic      (cli/parse-opts ["-avv" "--beta" "bee"
                                             "--no-daemon" "-f" "one"
                                             "--file=two" "arg"]
                                            option-specs)
                 no-default (cli/parse-opts ["--alpha"] option-specs
                                            :no-defaults true)
                 subcommand (cli/parse-opts ["--alpha" "serve" "--beta" "x"]
                                            option-specs
                                            :subcommand :explicit)]
             {:basic (select-keys basic [:options :arguments :errors])
              :no-default (select-keys no-default [:options :arguments :errors])
              :subcommand (select-keys subcommand [:options :arguments :errors])}))

(emit-case :parse-opts-error-boundaries
           {:unknown (select-keys (cli/parse-opts ["--missing"] option-specs)
                                  [:options :arguments :errors])
            :missing-arg (select-keys (cli/parse-opts ["--beta"] option-specs)
                                      [:options :arguments :errors])
            :strict-missing (select-keys (cli/parse-opts ["--beta" "--alpha"]
                                                         option-specs
                                                         :strict true)
                                         [:options :arguments :errors])
            :validation (select-keys (cli/parse-opts ["--beta" ""]
                                                   option-specs)
                                     [:options :arguments :errors])})

(emit-case :adversarial-subcommand-and-in-order
           {:in-order (select-keys (cli/parse-opts ["-a" "foo" "-b"]
                                                   [["-a" "--alpha"]
                                                    ["-b" "--beta"]]
                                                   :in-order true)
                                   [:options :arguments :errors])
            :explicit-positional (select-keys (cli/parse-opts ["-a" "foo" "-b"]
                                                              [["-a" "--alpha"]
                                                               ["-b" "--beta"]]
                                                              :subcommand :explicit)
                                              [:options :arguments :errors])
            :implicit-positional (select-keys (cli/parse-opts ["-a" "foo" "-b"]
                                                              [["-a" "--alpha"]
                                                               ["-b" "--beta"]]
                                                              :subcommand :implicit)
                                              [:options :arguments :errors])
            :explicit-no-positional (select-keys (cli/parse-opts ["-a" "-b"]
                                                                 [["-a" "--alpha"]]
                                                                 :subcommand :explicit)
                                                 [:options :arguments :errors])
            :implicit-unknown-start (select-keys (cli/parse-opts ["-a" "-b"]
                                                                 [["-a" "--alpha"]]
                                                                 :subcommand :implicit)
                                                 [:options :arguments :errors])
            :implicit-first-unknown (select-keys (cli/parse-opts ["-a" "foo" "-b"]
                                                                 [["-b" "--beta"]]
                                                                 :subcommand :implicit)
                                                 [:options :arguments :errors])
            :in-order-plus-subcommand-error? (errors?
                                              #(cli/parse-opts ["-a"]
                                                               [["-a" "--alpha"]]
                                                               :in-order true
                                                               :subcommand :explicit))})

(emit-case :adversarial-defaults-validation-and-summary
           {:default-fn (select-keys
                         (cli/parse-opts ["--host" "example.com"]
                                         [["-H" "--host HOST"
                                          :default "localhost"]
                                          ["-p" "--port PORT"
                                           :default-fn (fn [opts]
                                                         (if (= "localhost" (:host opts))
                                                           80
                                                           443))]
                                          ["-q" "--quiet"
                                           :default true]])
                         [:options :arguments :errors])
            :default-fn-no-defaults (select-keys
                                     (cli/parse-opts ["--host" "example.com"]
                                                     [["-H" "--host HOST"
                                                      :default "localhost"]
                                                      ["-p" "--port PORT"
                                                       :default-fn (fn [opts]
                                                                     (if (= "localhost" (:host opts))
                                                                       80
                                                                       443))]
                                                      ["-q" "--quiet"
                                                       :default true]]
                                                     :no-defaults true)
                                     [:options :arguments :errors])
            :missing (select-keys (cli/parse-opts []
                                                  [[nil "--required VALUE"
                                                    :missing "Required value missing"]])
                                  [:options :arguments :errors])
            :post-validation-success (select-keys
                                      (cli/parse-opts ["--tag" "a" "--tag" "b"]
                                                      [[nil "--tag TAG"
                                                        :default []
                                                        :update-fn conj
                                                        :multi true
                                                        :post-validation true
                                                        :validate [#(= 2 (count %))
                                                                   "Need exactly two tags"]]])
                                      [:options :arguments :errors])
            :post-validation-error (select-keys
                                    (cli/parse-opts ["--tag" "a"]
                                                    [[nil "--tag TAG"
                                                      :default []
                                                      :update-fn conj
                                                      :multi true
                                                      :post-validation true
                                                      :validate [#(= 2 (count %))
                                                                 "Need exactly two tags"]]])
                                    [:options :arguments :errors])
            :summary-fn (:summary (cli/parse-opts []
                                                  [["-a" "--alpha"]
                                                   ["-b" "--beta"]]
                                                  :summary-fn
                                                  (fn [specs]
                                                    (str "ids="
                                                         (str/join ","
                                                                   (map (comp name :id) specs))))))})

(emit-case :summary-and-formatting-helpers
           {:defaults (cli/get-default-options option-specs)
            :summary (cli/summarize compiled-summary-specs)
            :summary-part (cli/make-summary-part true
                                                 {:short-opt "-p"
                                                  :long-opt "--port"
                                                  :required "PORT"
                                                  :desc "Port"
                                                  :default 8080})
            :format-lines (vec (cli/format-lines [5 4]
                                                 [["-a" "AA"]
                                                  ["--bb" "BB"]]))})

(emit-case :legacy-cli
           (let [[options arguments banner] (cli/cli ["-p" "8080" "-v" "tail"]
                                                     ["-p" "--port" "Port"
                                                      :parse-fn count]
                                                     ["-v" "--verbose" "Verbose"
                                                      :flag true])]
             {:options options
              :arguments arguments
              :banner (str/replace banner #"\r\n" "\n")}))
