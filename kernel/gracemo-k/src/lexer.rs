use thiserror::Error;

#[derive(Debug, PartialEq, Clone)]
pub enum Token {
    Ident(String),
    StringLit(String),
    NumberLit(f64),
    BoolLit(bool),
    DoubleColon, // ::
    Pipe,        // |
    Colon,       // :
    Comma,       // ,
    LBracket,    // [
    RBracket,    // ]
    LParen,      // (
    RParen,      // )
}

#[derive(Error, Debug, PartialEq)]
pub enum LexerError {
    #[error("Unterminated string literal at position {0}")]
    UnterminatedString(usize),
    #[error("Unexpected character '{0}' at position {1}")]
    UnexpectedChar(char, usize),
    #[error("Invalid number literal at position {0}")]
    InvalidNumber(usize),
}

pub struct Lexer<'a> {
    _input: &'a str,
    chars: Vec<(usize, char)>,
    pos: usize,
}

impl<'a> Lexer<'a> {
    pub fn new(input: &'a str) -> Self {
        Self {
            _input: input,
            chars: input.char_indices().collect(),
            pos: 0,
        }
    }

    pub fn tokenize(&mut self) -> Result<Vec<Token>, LexerError> {
        let mut tokens = Vec::new();

        while self.pos < self.chars.len() {
            let (idx, c) = self.chars[self.pos];

            if c.is_whitespace() {
                self.pos += 1;
                continue;
            }

            match c {
                '|' => {
                    tokens.push(Token::Pipe);
                    self.pos += 1;
                }
                ':' => {
                    if self.pos + 1 < self.chars.len() && self.chars[self.pos + 1].1 == ':' {
                        tokens.push(Token::DoubleColon);
                        self.pos += 2;
                    } else {
                        tokens.push(Token::Colon);
                        self.pos += 1;
                    }
                }
                ',' => {
                    tokens.push(Token::Comma);
                    self.pos += 1;
                }
                '[' => {
                    tokens.push(Token::LBracket);
                    self.pos += 1;
                }
                ']' => {
                    tokens.push(Token::RBracket);
                    self.pos += 1;
                }
                '(' => {
                    tokens.push(Token::LParen);
                    self.pos += 1;
                }
                ')' => {
                    tokens.push(Token::RParen);
                    self.pos += 1;
                }
                '"' | '\'' => {
                    let quote_char = c;
                    let start_idx = idx;
                    self.pos += 1;
                    let mut s = String::new();
                    let mut closed = false;

                    while self.pos < self.chars.len() {
                        let (_, ch) = self.chars[self.pos];
                        if ch == quote_char {
                            closed = true;
                            self.pos += 1;
                            break;
                        } else if ch == '\\' && self.pos + 1 < self.chars.len() {
                            self.pos += 1;
                            s.push(self.chars[self.pos].1);
                            self.pos += 1;
                        } else {
                            s.push(ch);
                            self.pos += 1;
                        }
                    }

                    if !closed {
                        return Err(LexerError::UnterminatedString(start_idx));
                    }
                    tokens.push(Token::StringLit(s));
                }
                '-' | '+' | '0'..='9' => {
                    let start_idx = idx;
                    let mut num_str = String::new();
                    num_str.push(c);
                    self.pos += 1;

                    while self.pos < self.chars.len() {
                        let (_, ch) = self.chars[self.pos];
                        if ch.is_ascii_digit() || ch == '.' {
                            num_str.push(ch);
                            self.pos += 1;
                        } else {
                            break;
                        }
                    }

                    let val: f64 = num_str.parse().map_err(|_| LexerError::InvalidNumber(start_idx))?;
                    tokens.push(Token::NumberLit(val));
                }
                'a'..='z' | 'A'..='Z' | '_' => {
                    let mut ident_str = String::new();
                    ident_str.push(c);
                    self.pos += 1;

                    while self.pos < self.chars.len() {
                        let (_, ch) = self.chars[self.pos];
                        if ch.is_alphanumeric() || ch == '_' {
                            ident_str.push(ch);
                            self.pos += 1;
                        } else {
                            break;
                        }
                    }

                    match ident_str.as_str() {
                        "true" => tokens.push(Token::BoolLit(true)),
                        "false" => tokens.push(Token::BoolLit(false)),
                        _ => tokens.push(Token::Ident(ident_str)),
                    }
                }
                _ => return Err(LexerError::UnexpectedChar(c, idx)),
            }
        }

        Ok(tokens)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lexer_simple_pipeline() {
        let mut lexer = Lexer::new(r#"nav::goto[target: "bedroom", speed: 0.45] | vision::scan"#);
        let tokens = lexer.tokenize().unwrap();
        assert_eq!(
            tokens,
            vec![
                Token::Ident("nav".to_string()),
                Token::DoubleColon,
                Token::Ident("goto".to_string()),
                Token::LBracket,
                Token::Ident("target".to_string()),
                Token::Colon,
                Token::StringLit("bedroom".to_string()),
                Token::Comma,
                Token::Ident("speed".to_string()),
                Token::Colon,
                Token::NumberLit(0.45),
                Token::RBracket,
                Token::Pipe,
                Token::Ident("vision".to_string()),
                Token::DoubleColon,
                Token::Ident("scan".to_string()),
            ]
        );
    }
}
