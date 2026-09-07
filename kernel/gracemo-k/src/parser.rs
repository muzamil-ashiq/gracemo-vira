use crate::ast::{KPipeline, KStage, KValue};
use crate::lexer::{Lexer, Token};
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ParserError {
    #[error("Unexpected end of input")]
    UnexpectedEOF,
    #[error("Expected {0}, got {1:?}")]
    ExpectedToken(String, Option<Token>),
    #[error("Invalid syntax: {0}")]
    InvalidSyntax(String),
}

pub struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, pos: 0 }
    }

    pub fn parse_str(input: &str) -> Result<KPipeline, String> {
        let mut lexer = Lexer::new(input);
        let tokens = lexer.tokenize().map_err(|e| e.to_string())?;
        let mut parser = Parser::new(tokens);
        parser.parse_pipeline().map_err(|e| e.to_string())
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos)
    }

    fn next(&mut self) -> Option<Token> {
        if self.pos < self.tokens.len() {
            let t = self.tokens[self.pos].clone();
            self.pos += 1;
            Some(t)
        } else {
            None
        }
    }

    fn expect(&mut self, expected: Token) -> Result<(), ParserError> {
        let next = self.next();
        if next.as_ref() == Some(&expected) {
            Ok(())
        } else {
            Err(ParserError::ExpectedToken(format!("{:?}", expected), next))
        }
    }

    pub fn parse_pipeline(&mut self) -> Result<KPipeline, ParserError> {
        let mut pipeline = KPipeline::new();

        if self.peek().is_none() {
            return Ok(pipeline);
        }

        let first_stage = self.parse_stage()?;
        pipeline = pipeline.pipe(first_stage);

        while let Some(Token::Pipe) = self.peek() {
            self.next(); // Consume '|'
            let next_stage = self.parse_stage()?;
            pipeline = pipeline.pipe(next_stage);
        }

        Ok(pipeline)
    }

    pub fn parse_stage(&mut self) -> Result<KStage, ParserError> {
        let noun = match self.next() {
            Some(Token::Ident(s)) => s,
            other => return Err(ParserError::ExpectedToken("Identifier (noun)".into(), other)),
        };

        self.expect(Token::DoubleColon)?;

        let verb = match self.next() {
            Some(Token::Ident(s)) => s,
            other => return Err(ParserError::ExpectedToken("Identifier (verb)".into(), other)),
        };

        let mut stage = KStage::new(noun, verb);

        // Optional arguments block: `[...]`
        if let Some(Token::LBracket) = self.peek() {
            self.next(); // Consume '['

            while let Some(tok) = self.peek() {
                if let Token::RBracket = tok {
                    break;
                }

                // Parse key
                let key = match self.next() {
                    Some(Token::Ident(k)) => k,
                    other => return Err(ParserError::ExpectedToken("Argument key identifier".into(), other)),
                };

                self.expect(Token::Colon)?;

                // Parse value
                let val = self.parse_value()?;
                stage = stage.with_arg(key, val);

                // Optional comma
                if let Some(Token::Comma) = self.peek() {
                    self.next();
                }
            }

            self.expect(Token::RBracket)?;
        }

        Ok(stage)
    }

    fn parse_value(&mut self) -> Result<KValue, ParserError> {
        match self.next() {
            Some(Token::StringLit(s)) => Ok(KValue::String(s)),
            Some(Token::NumberLit(n)) => Ok(KValue::Number(n)),
            Some(Token::BoolLit(b)) => Ok(KValue::Bool(b)),
            Some(Token::LParen) => {
                // Coordinate tuple: `(x, y)` or `(x, y, z)`
                let x = match self.next() {
                    Some(Token::NumberLit(n)) => n,
                    other => return Err(ParserError::ExpectedToken("Number for x coordinate".into(), other)),
                };
                self.expect(Token::Comma)?;
                let y = match self.next() {
                    Some(Token::NumberLit(n)) => n,
                    other => return Err(ParserError::ExpectedToken("Number for y coordinate".into(), other)),
                };

                let z = if let Some(Token::Comma) = self.peek() {
                    self.next();
                    match self.next() {
                        Some(Token::NumberLit(n)) => Some(n),
                        other => return Err(ParserError::ExpectedToken("Number for z coordinate".into(), other)),
                    }
                } else {
                    None
                };

                self.expect(Token::RParen)?;
                Ok(KValue::Coordinates { x, y, z })
            }
            other => Err(ParserError::ExpectedToken("Literal Value".into(), other)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_pipeline() {
        let input = r#"graph::locate[entity: "Coke"] | nav::reach[target: (-5.0, 1.4), clearance: 0.5] | vision::scan"#;
        let pipeline = Parser::parse_str(input).unwrap();
        assert_eq!(pipeline.stages.len(), 3);

        assert_eq!(pipeline.stages[0].noun, "graph");
        assert_eq!(pipeline.stages[0].verb, "locate");
        assert_eq!(
            pipeline.stages[0].args.get("entity"),
            Some(&KValue::String("Coke".to_string()))
        );

        assert_eq!(pipeline.stages[1].noun, "nav");
        assert_eq!(pipeline.stages[1].verb, "reach");
        assert_eq!(
            pipeline.stages[1].args.get("target"),
            Some(&KValue::Coordinates { x: -5.0, y: 1.4, z: None })
        );

        assert_eq!(pipeline.stages[2].noun, "vision");
        assert_eq!(pipeline.stages[2].verb, "scan");
    }
}
