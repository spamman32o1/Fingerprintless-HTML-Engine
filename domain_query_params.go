package main

import (
	"bufio"
	"flag"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

var linkAttrRegex = regexp.MustCompile(`(?i)(?:href|src)=['"]?([^'">\s]+)`)

func main() {
	domainsPath := flag.String("domains", "", "Path to file containing domains (one per line)")
	maxPages := flag.Int("max-pages", 100, "Maximum pages to crawl per domain")
	timeout := flag.Duration("timeout", 10*time.Second, "HTTP request timeout")
	scheme := flag.String("scheme", "https", "Default scheme when domain lacks one")
	flag.Parse()

	if *domainsPath == "" {
		fmt.Fprintln(os.Stderr, "-domains flag is required")
		os.Exit(1)
	}

	workers := promptWorkers(os.Stdin, os.Stdout)

	file, err := os.Open(*domainsPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to open domains file: %v\n", err)
		os.Exit(1)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		domain := strings.TrimSpace(scanner.Text())
		if domain == "" || strings.HasPrefix(domain, "#") {
			continue
		}

		fmt.Printf("\n==> Processing domain %q\n", domain)
		params, err := crawlDomain(domain, *scheme, workers, *maxPages, *timeout)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error processing %q: %v\n", domain, err)
			continue
		}

		if len(params) == 0 {
			fmt.Println("No query parameters found.")
			continue
		}

		sorted := make([]string, 0, len(params))
		for param := range params {
			sorted = append(sorted, param)
		}
		sort.Strings(sorted)
		fmt.Println("Query parameters found:")
		for _, param := range sorted {
			fmt.Printf("- %s\n", param)
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "error reading domains file: %v\n", err)
		os.Exit(1)
	}
}

func promptWorkers(in *os.File, out *os.File) int {
	reader := bufio.NewReader(in)
	for {
		fmt.Fprint(out, "Enter number of workers: ")
		line, err := reader.ReadString('\n')
		if err != nil {
			fmt.Fprintf(os.Stderr, "failed to read workers: %v\n", err)
			os.Exit(1)
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		workers, err := strconv.Atoi(line)
		if err != nil || workers <= 0 {
			fmt.Fprintln(out, "Please enter a positive integer.")
			continue
		}
		return workers
	}
}

func crawlDomain(domain, defaultScheme string, workers, maxPages int, timeout time.Duration) (map[string]struct{}, error) {
	startURL, err := ensureURL(domain, defaultScheme)
	if err != nil {
		return nil, err
	}

	baseHost := startURL.Hostname()
	client := &http.Client{Timeout: timeout}
	params := make(map[string]struct{})
	visited := make(map[string]struct{})
	var mu sync.Mutex
	jobs := make(chan string, maxPages)
	var urlWg sync.WaitGroup

	enqueue := func(raw string) {
		mu.Lock()
		if _, ok := visited[raw]; ok {
			mu.Unlock()
			return
		}
		if len(visited) >= maxPages {
			mu.Unlock()
			return
		}
		visited[raw] = struct{}{}
		mu.Unlock()
		urlWg.Add(1)
		jobs <- raw
	}

	enqueue(startURL.String())

	var workersWg sync.WaitGroup
	for i := 0; i < workers; i++ {
		workersWg.Add(1)
		go func() {
			defer workersWg.Done()
			for raw := range jobs {
				processURL(raw, baseHost, client, &mu, params, enqueue)
				urlWg.Done()
			}
		}()
	}

	go func() {
		urlWg.Wait()
		close(jobs)
	}()

	workersWg.Wait()
	return params, nil
}

func ensureURL(domain, defaultScheme string) (*url.URL, error) {
	if !strings.Contains(domain, "://") {
		domain = fmt.Sprintf("%s://%s", defaultScheme, domain)
	}
	parsed, err := url.Parse(domain)
	if err != nil {
		return nil, fmt.Errorf("invalid domain %q: %w", domain, err)
	}
	if parsed.Host == "" {
		return nil, fmt.Errorf("invalid domain %q", domain)
	}
	return parsed, nil
}

func processURL(raw, baseHost string, client *http.Client, mu *sync.Mutex, params map[string]struct{}, enqueue func(string)) {
	parsed, err := url.Parse(raw)
	if err != nil {
		return
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return
	}
	collectQueryParams(parsed, mu, params)

	resp, err := client.Get(parsed.String())
	if err != nil {
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return
	}

	body, err := readBodyLimit(resp, 2*1024*1024)
	if err != nil {
		return
	}

	links := linkAttrRegex.FindAllStringSubmatch(string(body), -1)
	for _, match := range links {
		if len(match) < 2 {
			continue
		}
		candidate := strings.TrimSpace(match[1])
		if candidate == "" || strings.HasPrefix(candidate, "javascript:") || strings.HasPrefix(candidate, "mailto:") {
			continue
		}
		resolved, err := parsed.Parse(candidate)
		if err != nil {
			continue
		}
		if resolved.Host == "" {
			continue
		}
		if !sameDomain(baseHost, resolved.Hostname()) {
			continue
		}
		collectQueryParams(resolved, mu, params)
		enqueue(resolved.String())
	}
}

func readBodyLimit(resp *http.Response, limit int64) ([]byte, error) {
	reader := bufio.NewReader(resp.Body)
	var builder strings.Builder
	var total int64
	buf := make([]byte, 4096)
	for {
		if total >= limit {
			break
		}
		toRead := int64(len(buf))
		remaining := limit - total
		if remaining < toRead {
			toRead = remaining
		}
		n, err := reader.Read(buf[:toRead])
		if n > 0 {
			builder.Write(buf[:n])
			total += int64(n)
		}
		if err != nil {
			break
		}
	}
	return []byte(builder.String()), nil
}

func collectQueryParams(parsed *url.URL, mu *sync.Mutex, params map[string]struct{}) {
	for key := range parsed.Query() {
		mu.Lock()
		params[key] = struct{}{}
		mu.Unlock()
	}
}

func sameDomain(baseHost, candidate string) bool {
	if baseHost == candidate {
		return true
	}
	return strings.HasSuffix(candidate, "."+baseHost)
}
